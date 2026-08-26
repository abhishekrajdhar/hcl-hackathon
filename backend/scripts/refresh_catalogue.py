"""Refresh the YouTube catalogue from the source of truth: YouTube itself.

Run this when adding videos or when runtimes/titles may have drifted:

    python scripts/refresh_catalogue.py        # writes /tmp/catalogue.json
    python scripts/gen_seed.py                 # regenerates app/db/seeds/resources.py

Fetches real title, channel and duration for every catalogue video.

Nothing is invented: a video that fails verification is dropped rather than
seeded with guessed metadata.
"""
import json, os, re, subprocess, time, concurrent.futures

# (video_id, primary skill slug, extra skill slugs, difficulty, type)
VIDEOS = [
 ("rfscVS0vtbw","python",["programming-fundamentals"],1,"course"),
 ("_uQrJ0TkZlc","python",[],1,"course"),
 ("kqtD5dpn9C8","programming-fundamentals",["python"],1,"video"),
 ("5NgNicANyqM","programming-fundamentals",["machine-learning"],3,"course"),
 ("RBSGKlAvoiM","data-structures-algorithms",[],3,"course"),
 ("8hly31xKli0","data-structures-algorithms",[],2,"course"),
 ("HXV3zeQKqGY","sql",[],2,"course"),
 ("RGOj5yH7evk","version-control-git",[],1,"course"),
 ("fNk_zzaMoSs","linear-algebra",[],3,"video"),
 ("WUvTyaaNkzM","calculus",[],3,"video"),
 ("IHZwWFHWa-w","optimization",["neural-networks"],4,"video"),
 ("Ilg3gGewQ5U","optimization",["neural-networks","deep-learning"],4,"video"),
 ("qBigTkBLU6g","probability",["statistics"],2,"video"),
 ("xxpc-HPKN28","statistics",["probability"],3,"course"),
 ("Gv9_4yMHFhI","machine-learning",[],2,"video"),
 ("ZyhVh-qRZPA","data-wrangling",["python"],2,"video"),
 ("vmEHCJofslg","data-wrangling",["python"],2,"course"),
 ("QUT1VHiLmmI","data-wrangling",["linear-algebra"],2,"course"),
 ("UO98lJQ3QGI","data-visualization",["python"],2,"video"),
 ("hSPmj7mK6ng","data-visualization",["python"],2,"video"),
 ("q8q3OFFfY6c","etl-pipelines",["python"],3,"video"),
 ("_C8kWso4ne4","big-data-spark",["etl-pipelines"],4,"course"),
 ("P8ERBy91Y90","feature-engineering",["data-wrangling"],3,"video"),
 ("ua-CiDNNj30","machine-learning",["statistics","data-wrangling"],2,"course"),
 ("i_LwzRVP7bg","machine-learning",["supervised-learning"],2,"course"),
 ("pqNCD_5r0IU","supervised-learning",["machine-learning"],3,"course"),
 ("4qVRBYAdLAo","supervised-learning",[],1,"video"),
 ("NxEHSAfFlK8","supervised-learning",["python"],3,"video"),
 ("4b5d3muPQmA","unsupervised-learning",[],3,"video"),
 ("4jRBRDbJemM","model-evaluation",[],3,"video"),
 ("J4Wdy0Wc_xQ","ensemble-methods",["supervised-learning"],4,"video"),
 ("ok2s1vV9XW0","ensemble-methods",["python"],3,"video"),
 ("efR1C6CvhmE","supervised-learning",["model-evaluation"],4,"video"),
 ("aircAruvnKk","neural-networks",[],3,"video"),
 ("dPWYUELwIdM","neural-networks",["deep-learning"],3,"course"),
 ("VMj-3S1tku0","neural-networks",["deep-learning","python"],4,"course"),
 ("bte8Er0QhDg","neural-networks",["python"],3,"video"),
 ("V_xro1bcAuA","pytorch",["deep-learning"],3,"course"),
 ("Z_ikDlimN6A","pytorch",["deep-learning"],3,"course"),
 ("tPYj3fFJGjk","deep-learning",["neural-networks"],3,"course"),
 ("WFr2WgN9_xE","deep-learning",["python","machine-learning"],3,"course"),
 ("oXlwWbU8l2o","image-processing",["python"],2,"course"),
 ("YCzL96nL7j0","rnn",["deep-learning"],4,"video"),
 ("4Bdc55j80l8","transformers",["deep-learning"],4,"video"),
 ("zxQyTK8quyY","transformers",["rnn"],5,"video"),
 ("dIUTsFT2MeQ","nlp-fundamentals",["python"],3,"course"),
 ("viZrOnJclY0","word-embeddings",["nlp-fundamentals"],3,"video"),
 ("kCc8FmEb1nY","language-models",["transformers","pytorch"],5,"course"),
 ("PaCmpygFfXo","language-models",["neural-networks"],5,"course"),
 ("LPZh9BOjkQs","large-language-models",[],2,"video"),
 ("zizonToFXDs","large-language-models",["generative-ai"],2,"video"),
 ("p3sij8QzONQ","fine-tuning-llms",["large-language-models"],5,"course"),
 ("T-D1OfcDW1M","rag-systems",["large-language-models"],3,"video"),
 ("JEBDfGqrAUA","rag-systems",["large-language-models"],4,"course"),
 ("yfHHvmaMkcA","rag-systems",["word-embeddings"],4,"course"),
 ("fqMOX6JJhGo","docker-containers",[],2,"course"),
 ("X48VuDVv0do","model-deployment",["docker-containers"],4,"course"),

 # --- systems, testing and tooling -------------------------------------------
 # Added after roadmaps for non-ML roles came back with "Self-study: X" items:
 # the role designer was routing learners through skills the catalogue could
 # not teach, so the plan named a milestone with nothing to actually do.
 ("yK1uBHPdp30","operating-systems",[],3,"course"),
 ("vBURTt97EkA","operating-systems",[],1,"video"),
 ("IPvYjXCsTg8","computer-networks",[],2,"course"),
 ("bj-Yfakjllc","computer-networks",[],1,"video"),
 ("cHYq1MRoyI0","testing-and-debugging",["python"],2,"course"),
 ("EgpLj86ZHFQ","testing-and-debugging",["python"],2,"video"),
 ("PNhq_4d-5ek","shell-scripting",[],1,"course"),
 ("Sx9zG7wa4FA","shell-scripting",[],2,"course"),

 # --- design ------------------------------------------------------------------
 ("c9Wg6Cb_YlU","user-interface-design",[],1,"course"),
 ("RYDiDpW2VkM","user-interface-design",[],3,"course"),

 # --- game development --------------------------------------------------------
 ("45MIykWJ-C4","graphics-programming",[],4,"course"),
 ("W3gAzLwfIP0","graphics-programming",[],3,"video"),
 ("XtQMytORBmM","game-development-frameworks",[],1,"course"),
 ("nGKd4yTP3M8","game-development-frameworks",[],2,"course"),
 ("G8AT01tuyrk","game-design-principles",[],1,"video"),
 ("iIOIT3dCy5w","game-design-principles",[],2,"video"),

 # --- data and ML gaps --------------------------------------------------------
 ("J326LIUrZM8","data-warehousing",["sql"],2,"course"),
 ("HKcEyHF1U00","data-warehousing",["sql"],3,"course"),
 ("KZe0C0Qq4p0","experiment-design",["statistics"],3,"course"),
 ("eiIhTbFP0ls","experiment-design",[],1,"video"),
 ("kPxASj5wJBY","recommender-systems",["machine-learning"],3,"course"),
 ("Ams4sEn50cw","recommender-systems",["machine-learning"],3,"video"),
 ("2XUhKpH0p4M","named-entity-recognition",["nlp-fundamentals"],2,"video"),
 ("JIz-hiRrZ2g","named-entity-recognition",["nlp-fundamentals","python"],3,"video"),
 ("IHq1t7NxS8k","image-segmentation",["pytorch","deep-learning"],4,"video"),
 ("sSx5Qujq0Fs","image-segmentation",["deep-learning"],3,"video"),
 ("iv-5mZ_9CPY","diffusion-models",["generative-ai"],3,"video"),
 ("H45lF4sUgiE","diffusion-models",["deep-learning"],4,"video"),
 ("ciqWMIf7Pz0","ci-cd-ml",["mlops-fundamentals"],4,"course"),
 ("9I8X-3HIErc","ci-cd-ml",["mlops-fundamentals"],3,"video"),
 ("YhRfgYH_AoU","prompt-engineering",["large-language-models"],1,"course"),
 ("5i2Hn8OG94o","prompt-engineering",[],2,"course"),
]

# Runtimes already verified by an earlier run, read back out of the generated
# seed. YouTube rate-limits the watch page after a burst of requests, and
# without this the script would "verify 0" and quietly regenerate an EMPTY
# catalogue — destroying good data because the network said no. A previously
# verified runtime is real data; falling back to it is not guessing.
def known_runtimes() -> dict[str, float]:
    path = os.path.join(os.path.dirname(__file__), "..", "app", "db", "seeds", "resources.py")
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        return {}
    return {
        vid: float(hours)
        for vid, hours in re.findall(
            r'_YT \+ "([\w-]{11})",\s*\n\s*\d+, ([\d.]+),', text
        )
    }


KNOWN = known_runtimes()


def runtime_hours(vid: str, attempts: int = 3) -> float | None:
    """Actual runtime, from the watch page. Retries through rate limiting."""
    url = f"https://www.youtube.com/watch?v={vid}"
    for attempt in range(attempts):
        page = subprocess.run(["curl","-s","-m","25","--compressed", url,
            "-H","User-Agent: Mozilla/5.0"], capture_output=True, text=True).stdout
        m = re.search(r'"lengthSeconds":"(\d+)"', page)
        if m:
            return round(int(m.group(1)) / 3600, 2)
        if "/sorry/" in page or "302 Moved" in page:
            time.sleep(5 * (attempt + 1))  # rate limited — back off and retry
    return None


def fetch(entry):
    vid, primary, extra, diff, rtype = entry
    url = f"https://www.youtube.com/watch?v={vid}"
    o = subprocess.run(["curl","-s","-m","15","--compressed",
        f"https://www.youtube.com/oembed?url={url}&format=json"],
        capture_output=True, text=True).stdout.strip()
    try:
        meta = json.loads(o)
    except Exception:
        # oEmbed is the existence check: no record, no resource.
        return None
    hours = runtime_hours(vid)
    if hours is None:
        hours = KNOWN.get(vid)
        if hours is None:
            return None
        print(f"  ! {vid}: runtime unavailable, keeping verified {hours}h")
    return {
        "id": vid, "title": meta["title"], "channel": meta["author_name"],
        "hours": hours, "primary": primary, "extra": extra,
        "difficulty": diff, "type": rtype,
    }


out = []
# Modest concurrency: YouTube starts serving captchas well before this many
# watch-page requests land in parallel.
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
    for r in ex.map(fetch, VIDEOS):
        if r: out.append(r)

if len(out) < len(VIDEOS) * 0.8:
    raise SystemExit(
        f"only {len(out)}/{len(VIDEOS)} verified — refusing to regenerate the "
        "catalogue from a bad run. Wait for the rate limit to clear and retry."
    )

json.dump(out, open("/tmp/catalogue.json","w"), indent=1)
print(f"verified {len(out)} / {len(VIDEOS)}")
for r in out[:6]:
    print(f"  {r['hours']:>5}h  {r['channel'][:20]:22} {r['title'][:60]}")
