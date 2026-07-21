import sqlite3
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import AgglomerativeClustering
from collections import defaultdict
import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics.pairwise import cosine_distances

def get_table_names():
    conn = sqlite3.connect('seed.sqlite')
    cursor = conn.cursor()

    cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
    results = cursor.fetchall()

    print('table results:', results)

    for table in results:
        table_name = table[0]
        cursor.execute(f'SELECT * FROM {table_name}')
        cols = [desc[0] for desc in cursor.description]
        print(f'\nTable: {table_name}')
        print('Columns:', cols)

    conn.close()
    return

def get_titles(date = '2026-07-20'):
    conn = sqlite3.connect('seed.sqlite')
    cursor = conn.cursor()

    cursor.execute(f'SELECT title, feed_source  FROM items WHERE date(published_at) = "{date}"')
    results = cursor.fetchall()

    conn.close

    return results







title_results = get_titles()

titles = [col[0] for col in title_results]
sources = [col[1] for col in title_results]

vectoriser = TfidfVectorizer(stop_words='english')
X = vectoriser.fit_transform(titles)

model = AgglomerativeClustering(
    n_clusters=None,
    distance_threshold=0.6,
    metric='cosine',
    linkage='average'
)
labels = model.fit_predict(X.toarray())

# 3. group titles by their cluster label
clusters = defaultdict(list)
for title, src, label in zip(titles, sources, labels):
    clusters[label].append((title,src))

# 4. print only clusters with more than one title
for label, group in clusters.items():
    if len(group) > 1:
        print(f"\nCluster {label}:")
        for ttile, src in group:
            print(f"  - [{src}]{title}")



# precompute the distance matrix ONCE, reuse for every threshold
D = cosine_distances(X.toarray())

thresholds = np.arange(0.1, 1.0, 0.05)
n_clusters = []
n_multi = []          # clusters with >1 item (actual merges)
largest = []          # size of biggest cluster (chaining detector)

for t in thresholds:
    model = AgglomerativeClustering(
        n_clusters=None, distance_threshold=t,
        metric="precomputed", linkage="average",
    )
    labels = model.fit_predict(D)
    sizes = np.bincount(labels)
    n_clusters.append(len(sizes))
    n_multi.append(int((sizes > 1).sum()))
    largest.append(int(sizes.max()))

fig, ax = plt.subplots(3, 1, figsize=(8, 9), sharex=True)
ax[0].plot(thresholds, n_clusters, marker="o"); ax[0].set_ylabel("total clusters")
ax[1].plot(thresholds, n_multi, marker="o");   ax[1].set_ylabel("multi-item clusters")
ax[2].plot(thresholds, largest, marker="o");   ax[2].set_ylabel("largest cluster")
ax[2].set_xlabel("distance_threshold")
plt.tight_layout(); plt.savefig("threshold_sweep.png", dpi=120)
plt.show()

