# Installing T3dmium

This guide covers installing T3dmium on **macOS running on Apple Silicon**
(M1, M2, M3, or M4 Macs). Right now that is the only ready-to-download build.
Intel Macs and Windows are planned but not available yet — see
[Other platforms](#other-platforms) at the bottom.

If you'd rather build the browser yourself instead of downloading it, see
[BUILDING.md](BUILDING.md).

## What you need

- A Mac with **Apple Silicon** (M1/M2/M3/M4).
- **macOS 12 (Monterey) or newer.**
- About a minute.

Not sure which chip you have? Click the Apple menu in the top-left corner →
**About This Mac**. If it lists a chip named "Apple M1," "M2," "M3," or "M4,"
you're on Apple Silicon and this build is for you. If it says "Intel," this
download won't run — see [Other platforms](#other-platforms).

## Step 1 — Download the DMG

Go to the [T3dmium Releases page](https://github.com/t3dboy/t3dmium/releases)
and download the latest **macOS Apple Silicon (arm64)** disk image. The file
name ends in `.dmg`.

## Step 2 — Open the disk image and install

1. Double-click the downloaded `.dmg` file. A window opens showing the
   **T3dmium** app and a shortcut to your **Applications** folder.
2. **Drag T3dmium onto the Applications folder.** That copies it in.
3. When the copy finishes, you can eject the disk image (drag it to the Trash /
   Eject, or right-click it in Finder → **Eject**) and delete the `.dmg`.

## Step 3 — The first launch (important)

The first time you open T3dmium, macOS will show a warning like *"T3dmium cannot
be opened because the developer cannot be verified"* or *"unidentified
developer."* **This is expected and does not mean anything is wrong.** Here's why
it happens and how to get past it.

### Why the warning appears

Apple only suppresses this warning for apps that have been **notarized** —
submitted to Apple and signed with a paid Apple Developer account. T3dmium is an
independent, open-source project and is distributed as an **ad-hoc signed** build
instead. That means macOS can confirm the app hasn't been tampered with since it
was signed, but it can't tie it to a registered Apple developer — so it plays it
safe and warns you.

You are not trusting an anonymous binary here: **the complete source code and the
exact build steps are public** at
[github.com/t3dboy/t3dmium](https://github.com/t3dboy/t3dmium). Anyone can read
what T3dmium does, and the project's [network audit](audit/) even proves it isn't
phoning home. Open-source auditability is a stronger guarantee than a signature
you can't inspect.

### How to open it the first time

**The easy way — right-click to open:**

1. Open your **Applications** folder in Finder.
2. **Right-click** (or hold **Control** and click) the **T3dmium** app.
3. Choose **Open** from the menu.
4. In the dialog that appears, click **Open** again.

That one-time approval tells macOS you trust this app. After that, T3dmium opens
normally every time — by double-clicking, from Launchpad, from the Dock, however
you like.

**If you don't see an "Open" button** (newer macOS versions sometimes hide it):

1. Try to open T3dmium once (double-click it) and dismiss the warning.
2. Open **System Settings** → **Privacy & Security**.
3. Scroll down to the **Security** section. You'll see a message about T3dmium
   being blocked, with an **Open Anyway** button next to it.
4. Click **Open Anyway**, then confirm.

## Step 4 — Confirm you have the right build (optional)

To double-check you installed the Apple Silicon build and that it's intact, open
the **Terminal** app and run:

```
file /Applications/T3dmium.app/Contents/MacOS/T3dmium
```

You should see `arm64` in the output. To confirm the app's signature is valid
(ad-hoc, as expected):

```
codesign --verify --verbose /Applications/T3dmium.app
```

A clean run with no errors means the signature checks out.

## Updating

T3dmium does **not** silently update itself in the background — that would be
exactly the kind of unrequested traffic the project exists to avoid. To update,
download the newest DMG from the
[Releases page](https://github.com/t3dboy/t3dmium/releases) and repeat the
install steps, replacing the old app in Applications. (An **opt-in** update check
— one you turn on and control — is the intended model going forward.)

## Uninstalling

T3dmium is a normal Mac app, so removing it is simple:

1. Quit T3dmium.
2. Open **Applications** in Finder and drag **T3dmium** to the Trash.
3. Empty the Trash.

If you also want to remove your profile data (settings, history, bookmarks, and
so on), delete this folder:

```
~/Library/Application Support/T3dmium
```

You can open it quickly in Finder with **Go** → **Go to Folder…** and pasting
that path. Removing it wipes your local T3dmium data permanently, so only do this
if you're sure.

## Other platforms

- **Intel (x86_64) Macs:** an Intel build is **planned but not yet available.**
  The current DMG will not run on Intel Macs.
- **Windows:** a Windows build is **planned but not yet available.**
- **Linux:** not currently a supported download target.

If you can't wait for a prebuilt binary, you can compile T3dmium from source on
your own machine — be aware it's a heavy, multi-hour Chromium build. See
[BUILDING.md](BUILDING.md).

---

Found a problem, or saw T3dmium make a network request it shouldn't? Please open
an issue — especially unexpected traffic, which the project treats as a serious
bug. See the [privacy leak template](.github/ISSUE_TEMPLATE/privacy_leak.md).
