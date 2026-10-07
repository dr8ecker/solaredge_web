# Copyright (c) 2026 8ecker.de
"""Read-only detection of a mandatory terms confirmation, never its acceptance."""

TERMS_VISIBLE = r"""() => {
  const visible = el => el && el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden';
  const scopes = Array.from(document.querySelectorAll('[role=dialog],[aria-modal=true]')).filter(visible);
  if (!scopes.length && document.body) scopes.push(document.body);
  return scopes.some(scope => {
    const text = (scope.innerText || '').normalize('NFKC').replace(/\s+/g, ' ');
    const updated = /(?:we['’]?ve|we have).{0,25}updated.{0,60}terms|(?:nutzungsbedingungen|geschäftsbedingungen).{0,60}(?:aktualisiert|geändert)|(?:aktualisiert|geändert).{0,60}(?:nutzungsbedingungen|geschäftsbedingungen)/i.test(text);
    const checkbox = Array.from(scope.querySelectorAll('input[type=checkbox],[role=checkbox]')).some(visible);
    const submit = Array.from(scope.querySelectorAll('button,[role=button],input[type=submit]')).some(el =>
      visible(el) && /^(Submit|Bestätigen|Zustimmen|Akzeptieren)$/i.test((el.innerText || el.value || el.getAttribute('aria-label') || '').trim()));
    return updated && checkbox && submit;
  });
}"""
