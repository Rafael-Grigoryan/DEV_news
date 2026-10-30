## 3.13.7

**Released on:** 2026-10-22

This is a patch release that:

- Uses the updatable Conscrypt APEX root certificate store on Android 14+ in
  `dart:io`, so that root CA additions and distrusts delivered via Google Play
  system updates are honored. (issue [#64696])
- Updates BoringSSL to pick up upstream security fixes, including blocking a
  number of compromised intermediate certificates and X.509 path validation
  fixes. (issue [#568000])

[#64696]: https://github.com/dart-lang/sdk/pull/64696
[#568000]: https://dart-review.googlesource.com/c/sdk/+/568000

## 3.13.6

**Released on:** 2026-10-20

This is a patch release that:

- Fixes an issue in dart2js codegen where a single Dart call was generating multiple calls in the compiled JS code. (issue [#64410])

## 3.13.5

**Released on:** 2026-09-29

This is a patch release that:

- Fixes an issue in dart2wasm where tree-shaking (TFA) erroneously removed
  reachable methods containing static JS interop calls (issue [#64153]).

[#64153]: https://github.com/dart-lang/sdk/issues/64153

## 3.13.4

**Released on:** 2026-09-15

This is a patch release that:

- Fixes crash during dart2js compilation when using --merge-fragments-threshold
  and --minify flags. (issue [#64150])

