"""Refresh the YouTube catalogue from the source of truth: YouTube itself.

Run this when adding videos or when runtimes/titles may have drifted:

    python scripts/refresh_catalogue.py        # writes /tmp/catalogue.json
    python scripts/gen_seed.py                 # regenerates app/db/seeds/resources.py

Fetches real title, channel and duration for every catalogue video.

Nothing is invented: a video that fails verification is dropped rather than
seeded with guessed metadata.
"""
import json, re, subprocess, concurrent.futures

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
]

def fetch(entry):
    vid, primary, extra, diff, rtype = entry
    url = f"https://www.youtube.com/watch?v={vid}"
    o = subprocess.run(["curl","-s","-m","15","--compressed",
        f"https://www.youtube.com/oembed?url={url}&format=json"],
        capture_output=True, text=True).stdout.strip()
    try:
        meta = json.loads(o)
    except Exception:
        return None
    page = subprocess.run(["curl","-s","-m","25","--compressed", url,
        "-H","User-Agent: Mozilla/5.0"], capture_output=True, text=True).stdout
    m = re.search(r'"lengthSeconds":"(\d+)"', page)
    if not m:
        return None
    hours = round(int(m.group(1)) / 3600, 2)
    return {
        "id": vid, "title": meta["title"], "channel": meta["author_name"],
        "hours": hours, "primary": primary, "extra": extra,
        "difficulty": diff, "type": rtype,
    }

out = []
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
    for r in ex.map(fetch, VIDEOS):
        if r: out.append(r)
        
json.dump(out, open("/tmp/catalogue.json","w"), indent=1)
print(f"verified {len(out)} / {len(VIDEOS)}")
for r in out[:6]:
    print(f"  {r['hours']:>5}h  {r['channel'][:20]:22} {r['title'][:60]}")
