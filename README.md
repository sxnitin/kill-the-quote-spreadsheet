# Kill the Quote Spreadsheet

Streamlit prototype for normalizing messy packaging vendor quotes with Gemini 2.0 Flash and Supabase.

## Local setup

1. In Supabase SQL Editor, execute `schema.sql`.
2. Create `.streamlit/secrets.toml` (never commit it):
   ```toml
   GEMINI_API_KEY = "..."
   SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
   SUPABASE_KEY = "YOUR_SERVICE_ROLE_KEY"
   ```
3. Run `pip install -r requirements.txt` and then `streamlit run app.py`.
4. Click **Re-seed Supabase**, then load each demo input or select **Extract with Gemini**.

## Streamlit Community Cloud deployment

1. Run `python github_deploy.py --repo kill-the-quote-spreadsheet --public` after setting `GITHUB_TOKEN`, or push this directory to an existing repository.
2. At https://share.streamlit.io, sign in with GitHub and select the repository, `main`, and `app.py`.
3. In **Advanced settings -> Secrets**, add the three TOML values above, then deploy. Streamlit shows the public URL.

Use a service-role key only in Streamlit secrets. Never expose or commit it.