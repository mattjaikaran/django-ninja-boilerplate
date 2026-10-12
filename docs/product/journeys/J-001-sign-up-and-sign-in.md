---
id: J-001
title: Sign up and sign in
actor: Visitor
status: building
steps:
  - id: S1
    title: Create an account
    story: As a visitor, I want to create an account, so that I can save my work.
    features: [F-001]
    acceptance:
      - The signup form accepts a username, an email, and a password.
      - The page confirms that a welcome email is on its way.
      - A weak password shows the validation message from the API.
  - id: S2
    title: Sign in
    story: As a returning user, I want to sign in with my email and password, so that I reach my data.
    features: [F-002]
    acceptance:
      - Valid credentials land me on the dashboard, signed in.
      - Invalid credentials show an error and keep me on the sign-in page.
  - id: S3
    title: Stay signed in
    story: As a signed-in user, I want my session to renew quietly, so that I am not signed out while I work.
    features: [F-003]
    acceptance:
      - After the access token expires, the next request still succeeds.
  - id: S4
    title: Sign out
    story: As a signed-in user, I want to sign out, so that nobody else can use my session.
    features: [F-004]
    acceptance:
      - Signing out returns me to the sign-in page.
      - A protected page then redirects to the sign-in page.
---

## Goal

A visitor creates an account, signs in, keeps the session across token
expiry, and signs out.

## Context

- Signup calls `POST /api/auth/signup`. It always answers 202 with the same
  message, so the page must not reveal whether the email is taken.
- Sign-in calls `POST /api/auth/login`. The response sets the httpOnly auth
  cookies. The page then loads the user from `GET /api/auth/me`.
- The client renews the session with `POST /api/auth/refresh`, which rotates
  the refresh token.
- Sign-out calls `POST /api/auth/logout`.

## Notes

Repeated failed sign-ins lock the account and the client IP for a while
(HTTP 429). The tests must use a fresh account per run.
