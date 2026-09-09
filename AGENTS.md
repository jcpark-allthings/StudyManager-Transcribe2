# Development boundaries

- Work only in StudyManager-Transcribe2. Never add the original repository as a remote or copy its private source/data.
- Preparation clients must not load AI runtimes or hold provider credentials. AI execution belongs to the Mac hub.
- Keep the authoritative queue database local to the Mac; exchange only immutable requests and results through shared storage.
- Real NAS configuration is deferred. Update docs/NAS_SETUP_LATER.md for future setup.
- Preserve raw outputs. Describe simulated tests separately from actual Mac/Windows/NAS verification.
- Run python -m unittest discover -s tests -v after workflow changes.
