# 018: Querying the Database (Bronze & Silver Layers)

## Context
When inspecting the raw data extracted by the scrapers (Bronze Layer), the article contents such as `title`, `description`, and `text` are stored in a `JSONB` column named `payload` within the `raw_articles` table.

Because this data is stored in `JSONB`, querying it requires specific PostgreSQL JSON operators (like `->>`). Furthermore, executing these queries directly from the host terminal via `docker compose exec` can lead to bash escaping issues (like the `column "title" does not exist` error) if single quotes are not handled correctly.

This playbook provides safe, public ways to explore the dataset and extract text or descriptions.

## Accessing the Database

To avoid string escaping issues in bash, it's highly recommended to drop directly into the `psql` interactive shell rather than passing the query as a `-c` string argument:

```bash
docker compose exec postgres psql -U syndra_user -d syndra_db
```

*(Note: Ensure you are using `syndra_user` and `syndra_db` as defined in your `.env` file.)*

## Useful Queries

Once inside the `psql` shell, you can run the following queries.

### 1. Get 100 Random Articles with Titles and Descriptions
To extract the `title` and `description` from the `JSONB` payload for successfully processed articles:

```sql
SELECT 
    payload->>'title' AS title, 
    payload->>'description' AS description
FROM raw_articles 
WHERE ingestion_state = 'processed' 
ORDER BY RANDOM() 
LIMIT 100;
```

### 2. Inspecting the Structure of the Payload
If you need to know exactly what fields are available inside the `payload` JSON (e.g. `text`, `content`, `published_at`, `is_vectorized`), you can list the keys of a single row:

```sql
SELECT jsonb_object_keys(payload) AS keys
FROM raw_articles
LIMIT 1;
```

### 3. Querying the Refined (Silver) Layer
If you just need titles along with their sentiment and tickers (and don't strictly need the raw description), you can query the refined `articles` table which exposes these as native columns:

```sql
SELECT title, sentiment_label, sentiment_score, tickers 
FROM articles 
ORDER BY RANDOM() 
LIMIT 100;
```

## Troubleshooting: Bash Escaping Errors

If you **must** run the query in a single line from the terminal (for a script or Makefile), avoid wrapping the `docker compose exec` shell command in single quotes (`'`) while also using single quotes for the SQL query strings. 

The error `ERROR: column "title" does not exist` happens when the shell prematurely evaluates the string, stripping the quotes around `'title'`, which causes PostgreSQL to treat it as a column name rather than a JSON key.

**Correct One-Liner (using double quotes for the query string):**
```bash
docker compose exec postgres psql -U syndra_user -d syndra_db --pset pager=off -c "
SELECT 
    payload->>'title' AS title, 
    payload->>'description' AS description 
FROM raw_articles 
WHERE ingestion_state = 'processed' 
ORDER BY RANDOM() 
LIMIT 100;
"
```
*Note: Using `--pset pager=off` prevents the output from hanging on `(END)` or `--More--` when the terminal screen fills up.*

## 4. Querying the Refined (Silver) Layer for Ticker Statistics
If you want to see a summary of sentiment distribution across tickers (Positive/Negative/Neutral) from the refined `articles` table (Silver Layer):

```bash
docker compose exec postgres psql -U syndra_user -d syndra_db --pset pager=off -c "
SELECT 
    t as ticker, 
    COUNT(*) as total_articles,
    SUM(CASE WHEN sentiment_label = 'positive' THEN 1 ELSE 0 END) as positive,
    SUM(CASE WHEN sentiment_label = 'negative' THEN 1 ELSE 0 END) as negative,
    SUM(CASE WHEN sentiment_label = 'neutral' THEN 1 ELSE 0 END) as neutral
FROM articles, unnest(tickers) as t
GROUP BY t
ORDER BY total_articles DESC
LIMIT 20;
"
```

### 5. Sample articles where ticker is known, for manual labeling

```sql
SELECT 
    a.id,
    r.payload->>'title' AS title,
    a.sentiment_label,
    a.sentiment_score,
    a.tickers
FROM articles a
JOIN raw_articles r ON a.raw_article_id = r.id
WHERE array_length(a.tickers, 1) > 0
ORDER BY RANDOM()
LIMIT 50;
```