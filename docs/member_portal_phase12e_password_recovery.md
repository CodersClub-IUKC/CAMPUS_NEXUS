# Member Portal Phase 12E Password Recovery

## Eligibility

Password recovery is only for active Django users that are linked to `Member` through `user.member_profile`. Staff-only, superuser-only, inactive, unlinked, and member records without a user are not eligible.

## Identifier Resolution

The Member Portal login serializer uses Django's configured `USERNAME_FIELD`; this project currently uses the stock `username`. Password reset accepts one field, `identifier`, trims surrounding whitespace, and resolves it against the same username field.

## Endpoints

- `POST /api/v1/auth/password-reset/request/` with `{ "identifier": "member.user" }`
- `POST /api/v1/auth/password-reset/validate/` with `{ "uid": "...", "token": "..." }`
- `POST /api/v1/auth/password-reset/confirm/` with `{ "uid": "...", "token": "...", "new_password": "...", "new_password_confirm": "..." }`

The request endpoint returns HTTP 202 and the same body for every syntactically valid request:

```json
{
  "detail": "If an eligible Campus Nexus account matches the information provided, password recovery instructions will be sent."
}
```

The validate endpoint returns only `{ "valid": true }` or `{ "valid": false }`. It never returns user, member, email, or registration data.

## Token Architecture

The backend uses Django's `default_token_generator`, `urlsafe_base64_encode`, `urlsafe_base64_decode`, and `force_bytes`. Plaintext reset tokens are not stored. Password changes invalidate the token naturally through Django's password-reset token state.

Frontend URL format:

```text
{MEMBER_PORTAL_ORIGIN}/reset-password/<uid>/<token>
```

Production must set `MEMBER_PORTAL_ORIGIN=https://member.campusnexus.codersug.com`.

## Email

Email delivery uses Django's configured email backend. Templates are:

- `templates/campus_nexus/email/password_reset_subject.txt`
- `templates/campus_nexus/email/password_reset_email.txt`
- `templates/campus_nexus/email/password_reset_email.html`

Subject: `Campus Nexus Password Recovery`

Production SMTP is environment-driven through `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_USE_SSL`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, and `DEFAULT_FROM_EMAIL`. Development defaults to Django's console email backend unless `EMAIL_BACKEND` is overridden.

Email delivery failures are logged server-side without logging reset URLs or tokens. The public API still returns the generic accepted response.

## Abuse Controls

The request endpoint uses DRF `ScopedRateThrottle` with scope `password_reset` and default rate `5/hour` per client IP. The confirm endpoint uses scope `password_reset_confirm` and default rate `10/hour`. Repeated sends to the same normalized identifier are additionally suppressed after `PASSWORD_RESET_IDENTIFIER_MAX_REQUESTS_PER_WINDOW` within `PASSWORD_RESET_IDENTIFIER_WINDOW_SECONDS`, without changing the public response.

The deployment does not trust arbitrary `X-Forwarded-For`. Django/DRF will use `REMOTE_ADDR` unless infrastructure is explicitly configured and reviewed.

## JWT And Sessions

After a successful password reset, all SimpleJWT `OutstandingToken` rows for that user are blacklisted. Current access tokens are stateless and remain valid until their configured expiry; the default lifetime is `SIMPLE_JWT_ACCESS_TOKEN_MINUTES=15`. Django sessions for that user are deleted. `update_session_auth_hash` is not used because this is a public reset flow, not an authenticated password-change form.

## AuditLog

Eligible internal reset requests create `MEMBER_PASSWORD_RESET_REQUESTED`. Successful resets create `MEMBER_PASSWORD_RESET_COMPLETED`. Audit metadata does not include plaintext passwords, reset tokens, JWTs, email bodies, or reset URLs.

## Local Testing

Use the default development console email backend or set:

```env
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
MEMBER_PORTAL_ORIGIN=http://localhost:5173
```

Then call the request endpoint and copy the printed reset URL into the Member Portal reset screen.

## Production Deployment

Required environment actions:

- Set `MEMBER_PORTAL_ORIGIN=https://member.campusnexus.codersug.com`.
- Configure SMTP environment variables with real provider values.
- Confirm `CORS_ALLOWED_ORIGINS` includes the member portal origin or rely on production settings to append `MEMBER_PORTAL_ORIGIN`.
- Tune password reset throttle rates only if operational evidence requires it.

Smoke test:

1. POST a known eligible username to `/api/v1/auth/password-reset/request/` and confirm HTTP 202 with the generic response.
2. Confirm exactly one email arrives with a `/reset-password/<uid>/<token>` link.
3. POST the `uid` and `token` to `/api/v1/auth/password-reset/validate/` and confirm `{ "valid": true }`.
4. POST matching strong passwords to `/api/v1/auth/password-reset/confirm/` and confirm success.
5. Confirm old password login fails and new password login succeeds.
6. Reuse the same reset token and confirm the backend rejects it.
7. Repeat the request for an unknown username and confirm the same generic response with no account details.
