from web import web_search, fetch_page

results = web_search("NCT03068754 ALS terminated")
for r in results:
    print(r["url"], "|", r["title"])
    print("   ", r["content"][:1000])

# %% second call: must be instant and print the same thing (read from cache)
results = web_search("NCT03068754 Acthar ALS terminated")
print(len(results), "results from cache")

# %% full text of the first hit
text = fetch_page(results[0]["url"])
print(len(text), "characters")
print(text[:2000])
# %%
