# BBC dataset goes here

No article data is included in this repository. Copy your BBC dataset into this directory using one of these layouts:

The bundled, ignored `bbc-fulltext.zip` was downloaded from the [dataset maintainer's repository](https://github.com/derekgreene/bbc-datasets). Its README states that the data is for non-commercial research use and that copyright in the original article text remains with the BBC. Cite D. Greene and P. Cunningham, “Practical Solutions to the Problem of Diagonal Dominance in Kernel Document Clustering,” ICML 2006, when using it.

```text
datasets/raw/bbc-news.csv
```

The CSV needs a category column (`category`, `label`, or `topic`) and a text column (`content`, `text`, `article`, or `body`). A `title` or `headline` column is optional.

Or use category folders containing `.txt` article files:

```text
datasets/raw/business/*.txt
datasets/raw/entertainment/*.txt
datasets/raw/politics/*.txt
datasets/raw/sport/*.txt
datasets/raw/tech/*.txt
```

Unzip archives before copying them here. Then run `python -m bigdata.cli datasets/raw` from the project root.
