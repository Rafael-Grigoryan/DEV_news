In general, our philosophy is to update the `stable` channel on a quarterly basis with feature updates. In the intervening period, occasionally we may decide a bug or regression warrants a hotfix. We tend to be extremely conservative with these hotfixes, since there's always a risk that fixing one bug introduces a new one, and we want the `stable` channel to always represent our most tested builds.

We intend to announce hotfixes to the [flutter-announce](https://groups.google.com/forum/#!forum/flutter-announce) group, and we recommend that you subscribe to that list if you publish an application using Flutter.

Note that we only hotfix the latest version -- if you see bugs on older versions of the `stable` channel, please consider moving to the latest `stable` channel version.

To ensure that you have the latest stable version with the hotfixes listed below, use the flutter tool at the command line as follows:

```
$ flutter channel stable
$ flutter upgrade
```

<!--
INTERNAL NOTE: DO **NOT** READ THIS FILE IN A TEST OR BUILDER.

As an optimization, `CHANGELOG.md`-only PRs skip almost all
tests, except `Linux analyze`. It is unsafe to read and use
this file in a test unless it is part of the Linux analyze
task (and that specific task, with that specific name).

INTERNAL NOTE: PLEASE DON'T JUST PASTE ISSUE TITLES!

Make sure that the text here helps customers understand
whether they are likely to be affected by the issue,
without them needing to read each issue individually.
Our goal is to make the list easy for them to scan.

More information and tips:
docs/releases/Hotfix-Documentation-Best-Practices.md
-->

## Flutter 3.47 Changes

### [3.47.9](https://github.com/flutter/flutter/releases/tag/3.47.9)
- [flutter/194570](https://github.com/flutter/flutter/issues/194570) When a path or command exceeds `MAX_PATH` on Windows (OS Error 206), `flutter_tools` crashed with an unhandled `ProcessPackageException` or `FileSystemException` instead of exiting cleanly with an actionable error message.
- [flutter/192933](https://github.com/flutter/flutter/issues/192933) When running `flutter test` in pub workspaces, monorepos, or symlinked directories on any platform, native assets compilation crashed with a `StateError`.
- [flutter/193527](https://github.com/flutter/flutter/issues/193527) When building custom text selection menus, packages can't add new actions such as Translate without breaking exhaustive switches on `ContextMenuButtonType`; adds the extensible `ContextMenuButtonKind`.

### [3.47.8](https://github.com/flutter/flutter/releases/tag/3.47.8)
#### Security advisory [GHSA-frr6-h895-5pxp](https://github.com/dart-lang/sdk/security/advisories/GHSA-frr6-h895-5pxp):
- [dart/568000](https://dart-review.googlesource.com/c/sdk/+/568000) Updates BoringSSL in the Dart runtime (3.13.7) to block compromised eMudhra intermediate CA certificates.
- [dart/64696](https://github.com/dart-lang/sdk/pull/64696) Updates `dart:io` on Android 14+ to use the updatable Conscrypt APEX root certificate store.
- Developers shipping Android, Windows, or Linux applications should upgrade to Flutter 3.47.8 and rebuild their apps.
---
- [flutter/190235](https://github.com/flutter/flutter/issues/190235) When running flutter pub get or building desktop apps with existing or broken plugin symlink entries, flutter_tools no longer crashes with a PathExistsException.
- [flutter/192934](https://github.com/flutter/flutter/issues/192934) When dumping the focus tree or layer tree from flutter run on any platform before the UI isolate finishes initializing or after teardown, flutter_tools crashed with a null check operator exception.

### [3.47.7](https://github.com/flutter/flutter/releases/tag/3.47.7)
- [flutter/182604](https://github.com/flutter/flutter/issues/182604) When an OverlayPortal is displayed on iOS, accessibility frames are shrunk by the device pixel ratio and anchored to the top-left, so VoiceOver focus and XCUITest taps miss the visible controls.
- [flutter/100946](https://github.com/flutter/flutter/issues/100946) When using VoiceOver on iOS with a ReorderableListView, Semantics focus is incorrectly shifted to the top left of the screen.

### [3.47.6](https://github.com/flutter/flutter/releases/tag/3.47.6)
- [flutter/192513](https://github.com/flutter/flutter/issues/192513) Fixed an issue that caused Windows production apps to hang.

### [3.47.5](https://github.com/flutter/flutter/releases/tag/3.47.5)
- [flutter/190307](https://github.com/flutter/flutter/issues/190307) When debugging on physical iOS 27 devices, app occasionally crashes.
- [flutter/191242](https://github.com/flutter/flutter/issues/191242) When re-expanding a preview group in the Widget Previewer, previews crash due to a type error in scroll restoration.
- [flutter/189507](https://github.com/flutter/flutter/pull/189507) When Dart Development Service encounters a startup failure, flutter_tools crashes with an unhandled FormatException.

### [3.47.4](https://github.com/flutter/flutter/releases/tag/3.47.4)
- [flutter/191899](https://github.com/flutter/flutter/issues/191899) When Windows Smart App Control or security policies block binary execution on Windows, gracefully handle the error with an actionable message instead of crashing.
- [flutter/192120](https://github.com/flutter/flutter/pull/192120) Fixes missing preview reload timing analytics in LspPreviewDetector across all platforms.
- [flutter/181560](https://github.com/flutter/flutter/issues/181560) When building iOS and macOS app, SwiftPM migration warnings and errors are not tracked in analytics.
- [flutter/191964](https://github.com/flutter/flutter/pull/191964) On iOS, apps bundling native assets fail App Store submission when native libraries are compiled with deployment targets above iOS 13.
- [flutter/189284](https://github.com/flutter/flutter/issues/189284) When debugging with Xcode 27, the app may launch to a white screen and hang for multiple minutes.
- [flutter/190465](https://github.com/flutter/flutter/issues/190465) When running WebAssembly dry-run builds on Web, remove redundant experiment flag warning that dropped telemetry error findings.
- [flutter/191898](https://github.com/flutter/flutter/issues/191898) When remote test processes emit plain-text error output on all platforms, prevent flutter_tools from crashing with an unhandled FormatException.

### [3.47.3](https://github.com/flutter/flutter/releases/tag/3.47.3)
- [flutter/191045](https://github.com/flutter/flutter/issues/191045) When calling Actions.handler on all platforms, null was always returned.
- [flutter/181315](https://github.com/flutter/flutter/issues/181315) When using Impeller on Android devices with B-Series PowerVR GPUs, visual oddities and performance drops can be experienced.
- [flutter/191176](https://github.com/flutter/flutter/issues/191176) When building for macOS or iOS on machines with missing or incomplete Xcode installations, flutter_tools displays an actionable error message instead of crashing with an unhandled ProcessException.
- [flutter/191487](https://github.com/flutter/flutter/issues/191487) When using Android SDK Command-line Tools 23.0+ for Android, flutter doctor incorrectly reports "Android license status unknown".

### [3.47.2](https://github.com/flutter/flutter/releases/tag/3.47.2)
- [flutter/191179](https://github.com/flutter/flutter/issues/191179) When WebSocket upgrade fails during DDS startup on web, handle the `DartDevelopmentServiceException` gracefully instead of crashing.
- [flutter/190518](https://github.com/flutter/flutter/pull/190518) Fix memory leak caused by processing touch events on Linux.
- [flutter/188265](https://github.com/flutter/flutter/issues/188265) iOS or macOS builds may fail when Swift Package Manager is enabled.
- [flutter/190846](https://github.com/flutter/flutter/issues/190846) When building an existing native iOS app that's integrated with Flutter using SwiftPM on Xcode 27, it may fail to build Flutter's Swift packages.
- [flutter/187925](https://github.com/flutter/flutter/issues/187925) On Linux, fix header elements not being announced by screen reader.
- [flutter/190774](https://github.com/flutter/flutter/issues/190774) When using external textures on Windows, a crash could occur when the engine paints them.
- [flutter/191177](https://github.com/flutter/flutter/issues/191177) The Flutter tool crashes if a configured custom device ping times out.
- [flutter/190987](https://github.com/flutter/flutter/issues/190987) Updates `libpng` to fix security vulnerability.
- [flutter/191060](https://github.com/flutter/flutter/issues/191060) When `analysis_options.yaml` contains flow-style `exclude:` sequences, `AnalysisOptionsMigration` converts the node to block style before appending to avoid `YamlEditor` assertion crashes.
- [flutter/191131](https://github.com/flutter/flutter/issues/191131) Only exclude platform directories that actually exist from analysis, so web/** sources in Dart web packages are no longer silently dropped.
- [flutter/191198](https://github.com/flutter/flutter/issues/191198) On Windows, truncate `lastCompiled` timestamp to whole seconds in `ProjectFileInvalidator` so rapid consecutive file modifications within the same second are not silently ignored by hot reload.
- [flutter/152236](https://github.com/flutter/flutter/issues/152236) On desktop platforms, forward `--build-name` and `--build-number` flags to the desktop build pipeline so generated `version.json` reflects command-line build version parameters.
- [flutter/191205](https://github.com/flutter/flutter/issues/191205) Prevent `StateError: Bad state: Future already completed in Symbolizer` during stack symbolization.
- [flutter/191178](https://github.com/flutter/flutter/issues/191178) Handle `HttpException` during VM service connection retries and ensure typed exceptions are passed to error completers.

### [3.47.1](https://github.com/flutter/flutter/releases/tag/3.47.1)
- [flutter/190871](https://github.com/flutter/flutter/issues/190871) Flutter GPU could not be enabled in release builds on Linux and Windows, since those embedders had no project-level opt-in and release builds ignore engine switches from the environment.
- [flutter/188446](https://github.com/flutter/flutter/issues/188446) When building multi-target applications in parallel on iOS and macOS, a race condition in SwiftPM integration causes `FileSystemException`.
- [flutter/189550](https://github.com/flutter/flutter/issues/189550) When running `flutter pub get` in a Dart workspace, platform tooling regeneration and analysis options migration are skipped for packages that do not depend on Flutter.
- [flutter/190234](https://github.com/flutter/flutter/issues/190234) Avoid crashing with `PathNotFoundException` when cleaning up native assets if files are removed concurrently.
- [flutter/189128](https://github.com/flutter/flutter/issues/189128) Invalidate `WebEntrypointTarget` and regenerate `web_plugin_registrant.dart` when web plugins are added or removed.
- [flutter/186445](https://github.com/flutter/flutter/issues/186445) Fix hot restart for WASM web builds.
- [flutter/190284](https://github.com/flutter/flutter/issues/190284) Fix hot reload failing to reload edits in nested Pub workspace member packages located under root `lib/`.
- [flutter/191056](https://github.com/flutter/flutter/issues/191056) Recursively resolve includes in `AnalysisOptionsMigration` to prevent redundant rewrites of `analysis_options.yaml`.
- [flutter/189156](https://github.com/flutter/flutter/issues/189156) Validate plugin class and package identifiers to prevent arbitrary code injection into `GeneratedPluginRegistrant`.
- [flutter/190721](https://github.com/flutter/flutter/issues/190721) Fix deadlock in debug adapters when the target process exits early during startup before VM service connection.
- [flutter/189972](https://github.com/flutter/flutter/issues/189972) Fix ADB device list parsing for long wireless mDNS serials separated from state by a single space.
- [flutter/190233](https://github.com/flutter/flutter/issues/190233) Fix `impellerc` crash on Windows when paths contain Unicode characters, and improve shader compiler error diagnostics.

### [3.47.0](https://github.com/flutter/flutter/releases/tag/3.47.0)

Learn about what's new in this release in [the blog post](https://flutter.dev/blog/whats-new-in-flutter-3-47), and check out the [CHANGELOG](https://docs.flutter.dev/release/release-notes/release-notes-3.47.0) for a detailed list of all the new changes.


## Flutter 3.44 Changes

### [3.44.9](https://github.com/flutter/flutter/releases/tag/3.44.9)
- [flutter/186366](https://github.com/flutter/flutter/issues/186366) When debugging an iOS app, if the app crashes, the Flutter CLI and tests that crash will hang.

### [3.44.8](https://github.com/flutter/flutter/releases/tag/3.44.8)
- [flutter/188346](https://github.com/flutter/flutter/issues/188346) When building on macOS or iOS using the Xcode 27 toolchain, the build will fail due to a lipo verification error.
- [flutter/184286](https://github.com/flutter/flutter/issues/184286) On some devices with vendor-modified Android 11 ROMs, `AccessibilityBridge.java` field fails to resolve.

### [3.44.7](https://github.com/flutter/flutter/releases/tag/3.44.7)
- [flutter/188161](https://github.com/flutter/flutter/issues/188161) Fixes a resource leak that sometimes caused crashes when using external textures on some GPUs (such as Arm Mali).

### [3.44.6](https://github.com/flutter/flutter/releases/tag/3.44.6)
- [flutter/187980](https://github.com/flutter/flutter/issues/187980) On Linux, building asset bundles with native assets enabled without a native app build directory crashes due to missing `CMakeCache.txt`.
- [flutter/188805](https://github.com/flutter/flutter/issues/188805) Fixes a crash when running Android instrumented tests.

### [3.44.5](https://github.com/flutter/flutter/releases/tag/3.44.5)
- [flutter/188718](https://github.com/flutter/flutter/issues/188718) When building Flutter Android apps and add-to-app modules using AGP < 9 with KGP, the tool incorrectly logs Built-in Kotlin migration warnings.
- [flutter/186810](https://github.com/flutter/flutter/issues/186810) [flutter/187388](https://github.com/flutter/flutter/issues/187388) [flutter/187553](https://github.com/flutter/flutter/issues/187553) When building Android app bundles using flavors, or with an old app template combined with a plugin coming alphabetically before app, fixes problems with failing to include libapp.so in the produced app bundle.
- [flutter/188035](https://github.com/flutter/flutter/issues/188035) When rendering text with shadows, the shadows would appear elsewhere on the screen, separate from the text.
- [flutter/187237](https://github.com/flutter/flutter/issues/187237) Fixes a crash that can happen during app shutdown or rotation on some Android devices using Impeller/Vulkan with HCPP.

### [3.44.4](https://github.com/flutter/flutter/releases/tag/3.44.4)
- [flutter/188192](https://github.com/flutter/flutter/issues/188192) Fix bounds checking in Flutter Linux's FlAccessibleTextField.

### [3.44.3](https://github.com/flutter/flutter/releases/tag/3.44.3)
- [flutter/186738](https://github.com/flutter/flutter/issues/186738) Demote flavor/platform asset skipping messages from warning to trace level to reduce build log noise.
- [flutter/186899](https://github.com/flutter/flutter/issues/186899) On Android, destroying a texture before the GLES fence that it holds was used may cause a crash.
- [flutter/186953](https://github.com/flutter/flutter/issues/186953) When building concurrently with SwiftPM on macOS/iOS, concurrent directory/file/symlink creation may cause a crash.
- [flutter/183179](https://github.com/flutter/flutter/issues/183179) Fixes an issue that can cause crashes when rendering animated PNG images.

### [3.44.2](https://github.com/flutter/flutter/releases/tag/3.44.2)
- [flutter/187322](https://github.com/flutter/flutter/issues/187322) When DTD connection is lost or fails at startup during widget-preview on all platforms, the tool crashes with unhandled exceptions instead of exiting gracefully.
- [flutter/186723](https://github.com/flutter/flutter/issues/186723) When Android apps switch from any `SystemUiMode` to edge-to-edge, the system bars unexpectedly remain invisible.
- [flutter/186054](https://github.com/flutter/flutter/issues/186054) When building an iOS or macOS app with Swift Package Manager enabled, remote package dependencies may fail to download.
- [flutter/185775](https://github.com/flutter/flutter/issues/185775) When building for non-iOS or macOS apps, Swift Package Manager warnings may appear.

### [3.44.1](https://github.com/flutter/flutter/releases/tag/3.44.1)
- [flutter/186962](https://github.com/flutter/flutter/issues/186962) When the analysis server exits unexpectedly, the `flutter` tool can crash instead of outputting a descriptive error message.
- [flutter/186963](https://github.com/flutter/flutter/issues/186963) When failing to connect to a Chrome instance on Windows, the `flutter` tool can crash instead of outputting a descriptive error message.

### [3.44.0](https://github.com/flutter/flutter/releases/tag/3.44.0)

Learn about what's new in this release in [the blog post](https://blog.flutter.dev/whats-new-in-flutter-3-44-b0cc1ad3c527), and check out the [CHANGELOG](https://docs.flutter.dev/release/release-notes/release-notes-3.44.0) for a detailed list of all the new changes.


