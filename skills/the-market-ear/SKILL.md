---
name: the-market-ear-newsfeed
description: Fetch stock market news from The Market Ear (https://themarketear.com/) (TME) and deduce how the stock market is doing.
---

# The Market Ear Newsfeed

If the user asks for stock market news from The Market Ear (https://themarketear.com/) (TME), then use this skill:
Execute the python script and dedeuct from its output how the stock market is doing.


## Usage

Set the token and run the script:

```bash
python3 skills/themarketear/themarketear_news.py --pages 1
```

To fetch more pages (infinite scroll):

```bash
python3 skills/themarketear/themarketear_news.py --pages 3
```

## Notes

- The script uses https requests with the `U` and `P` cookies derived from `TME_TOKEN`.
- Images are ignored; only titles and descriptions are printed.

## Default

If no number of pages is specified by the user, then 5 page are retrieved.
