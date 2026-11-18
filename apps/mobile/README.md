# `apps/mobile` — Flutter ask/answer client

Target role (see `CONTEXT.md` §2): **send a question, receive a grounded
answer**. No reconstruction, detection, tracking, simulation, promotion or
memory mutation. Capture remains a laptop CLI (`aegis-ingest`).

Layout:

| Path | Role |
|---|---|
| `lib/main.dart` | App entry point; creates `ApiService` and the material app. |
| `lib/services/api_service.dart` | HTTP client; `ask(text)` posts to `/api/v1/ask`, optional `health()` to find the server. 5 s timeout; unreachable server returns a clear message, never invented data. |
| `lib/views/` | Ask screen (text field + answer card). |
| `lib/models/` | Answer/evidence view models. |
| `lib/theme/` | Apple HIG-inspired design tokens (inset cards, 44 pt targets, type scale). |
| `test/` | Widget tests using a mocked HTTP client. |

Commands: `flutter pub get`, `flutter run` (USB/`adb reverse`),
`flutter analyze --no-fatal-infos`, `flutter test`. Flutter is not installed
on this development machine; CI runs the Dart checks.

Tests: `test/widget_test.dart`.
