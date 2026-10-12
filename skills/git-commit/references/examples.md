# Commit Message Examples

## Good

```
feat(auth): add token refresh on 401 responses

The client used to require a manual re-login after access tokens
expired. Intercept 401s and retry once with a refreshed token so
long-running sessions survive expiry.
```

```
fix(tools)!: reject paths escaping the workspace

BREAKING CHANGE: relative paths resolving outside WORKDIR now fail
instead of being silently clamped to the root.
```

## Bad

```
Fixed stuff
```

Why bad: no type/scope, past tense, vague subject, no body.

```
feat: Added New Feature, Updated Tests And Docs.
```

Why bad: subject not imperative/lowercase, trailing period, too long.
