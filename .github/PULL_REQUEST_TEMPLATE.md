## Summary

Describe the user-visible change and why it is needed.

## Verification

- [ ] `TMUX_TMPDIR=/tmp/nx-tests .venv/bin/python -m unittest discover -s tests` passes
- [ ] No secrets, private chats, personal data, or real project data were added
- [ ] New UI strings use `t('English', 'Русский')`, `static/i18n/source.json`, and every `static/i18n/<lang>.js`
- [ ] Claims about supported platforms and agent integrations match actual checks

## Screenshots or notes

Use demonstration data and say which platform and workflow were actually tested.
