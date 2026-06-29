# Tailscale Remote Access (v0.9.1)

Tailscale gives your phone a private, secure URL to the Streamlit frontend
running on your PC — without opening ports to the internet.

## Setup

1. Install Tailscale on your PC and your phone.
2. Log in to the **same** Tailscale account on both.
3. Run Streamlit bound to localhost:
   ```
   streamlit run app/main.py --server.address 127.0.0.1 --server.port 8501
   ```
4. Expose it over Tailscale:
   ```
   tailscale serve --bg 8501
   ```
5. From your phone (on Tailscale), open the Tailscale URL for your PC.

## Notes

- Tailscale is used for **frontend access**; Telegram is used for **control**
  (status / restart).
- The supervisor can optionally report whether the `tailscale` command exists
  and whether `tailscale status` succeeds, but **Tailscale is not required** for
  the local supervisor to work.
- v0.9.1 does not aggressively automate Tailscale — set it up once and leave it
  running at startup.
