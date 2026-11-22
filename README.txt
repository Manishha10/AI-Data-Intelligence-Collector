# AI Data Intelligence — One-Run Collector

This script collects public startup, product, research-paper, AI-news and AI-job records into a six-tab Excel workbook.

## Run on Windows

1. Install Python 3.10 or newer from https://www.python.org/downloads/
2. Extract this ZIP file.
3. Open the extracted folder.
4. In the folder address bar, type `cmd` and press Enter.
5. Run:

```bash
py -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
python collect_data.py
```

The result will be saved in `output/AI_Data_Intelligence_Collected.xlsx`, with `output/collection_summary.json`.

## Sources used

- Startups: public GitHub repository `yigitmeteozcan/startups` (the script discovers CSV/JSON files in the repository).
- Products: AGIPicks public verified AI tools dataset, CC BY 4.0: https://agipicks.com/data/
- Research papers: official arXiv API, AI-related categories cs.AI, cs.LG and cs.CL.
- News: The World of AI daily feed, OpenAI, TechCrunch AI, Google DeepMind and The Decoder RSS feeds.
- Jobs: Himalayas public jobs API, MOAI Jobs RSS, Remotive API, RemoteOK API and Arbeitnow API.

## Important limitations — read before submitting

- This is a collector, not a guarantee that every target will be met on every run. Public APIs and feeds change, rate-limit requests, and may return fewer records.
- The script prints exact counts. The 1,000-startup, 1,000-product and 1,000-paper requirements are met only if the output counts reach those numbers.
- News and jobs are filtered strictly using source-provided publication dates from the 24 hours before the run. A feed with no reliable date is excluded. The result is a snapshot at run time and will change tomorrow.
- GitHub stars are only added when a GitHub repository URL is explicitly found in the paper's arXiv metadata. Missing repository links/stars are left blank, not guessed.
- Some news sites may block full-text extraction or provide only a summary. Check the `content.fullText` column before claiming full-text coverage.
- Startup source fields may vary; inspect source URLs and the output before submission.
- Respect each source's terms, robots rules and rate limits. Do not bypass logins, CAPTCHAs or access controls.
- Attribute AGIPicks data as required by its CC BY 4.0 license.
- Do not publish private API keys or credentials in GitHub.

## Before submission

Open `collection_summary.json`. Confirm that Startups, Products and Research Papers each have at least 1,000 rows. Inspect the News and Jobs dates and source URLs. Remove any record you cannot verify. If a target is short, report the actual count rather than padding the sheet with invented data.
