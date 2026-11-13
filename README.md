# Diwali School Skit soundboard

An iPhone home-screen app that follows the skit scene by scene and tells you exactly when to press play.

**Open on the iPhone:** https://diwali-skit-sounds.netlify.app

The same app is also served from GitHub Pages at https://mineshamin1.github.io/skit-soundboard/.

## Put it on the iPhone (one time)

1. Open the Netlify link above in **Safari** on the iPhone.
2. Tap "Tap to load sounds" once and wait until the badge in the top right says "offline ok".
3. Tap Share, then "Add to Home Screen".
4. Turn on airplane mode and open it from the home screen icon to check it still works.

## How to use it during the show

- **Scene bar** at the top shows the scene you are in. The arrows jump to the previous or next scene.
- **Script** shows only the current scene. The words to wait for are highlighted in amber, followed by the green tag of the sound to play.
- **Amber strip** above the button says exactly when to press, for example "Play right after SUNDER says ...".
- **Big green button** plays that sound and moves to the next cue.
- When a scene's sounds are done, the button turns purple and says **Go to Scene N**. Tap it when the next scene starts. It plays nothing. A scene with no sounds works the same way.
- **Quick pad** shows only this scene's sounds. Tap one to play it again right away, for example an extra laugh. It does not move the cue.
- **Back** moves one cue back without playing. **Stop all** cuts every sound, including the long galti song.
- **Scenes tab** lists every scene. Tap a scene to jump to it, or tap a cue in the current scene. It also has a button for every sound, for emergencies.
- A second tap on the big button within under a second is ignored, so a nervous double tap fires only once.
- The app remembers where you are if it is closed by accident.

## Show-day checklist

- Ringer switch on, volume all the way up
- Do Not Disturb on, Auto-Lock set to Never, Low Power Mode off
- Cable plugged into the speakers or mixer
- Open the app from the home screen icon, not from Safari
- Tap "Tap to load sounds", check you are on Scene 1, cue 1
- Optional: Settings, Accessibility, Guided Access on, then triple-click the side button to lock the phone into the app

## Changing the script or sounds

1. Replace `input/script.docx` and/or the MP3s in `sounds/` (keep `sounds/_silence.mp3`). The script tag `haha` is mapped to `laughter.mp3` in `input/aliases.json`.
2. Rebuild the cues:

   ```bash
   python tools/build_cues.py --script input/script.docx --sounds sounds
   ```

3. Check `CUE_SHEET.md`: every cue, its sound file and when to play it, grouped by scene.
4. In `sw.js`, raise the cache number, for example `skit-soundboard-v8` to `skit-soundboard-v9`.
5. Commit and push. This updates the GitHub Pages copy.
6. Update the Netlify copy by deploying only the app files: `index.html`, `sw.js`, `manifest.webmanifest`, `cues.json`, the three icons and `sounds/`. Leave out `input/`, `tools/`, `CUE_SHEET.md` and `.git`. Put them in one folder and run:

   ```bash
   npx netlify-cli deploy --prod --dir <that folder> --site c8c83116-58d4-4d5f-80e2-a8b915c73b21
   ```

7. Open the app once on the phone while online so it downloads the new version.

### Script rules

- Scenes start with a paragraph like `SCENE 3: Money or Intelligence?`.
- Dialogue lines look like `GURUJI: words` or `Alok (waking up): words`.
- Sound cues look like `[SFX: haha]` and match `sounds/haha.mp3`. Case, spaces, dashes and underscores are ignored.
- If a tag and a file name differ, map them in `input/aliases.json`, for example `{"big laugh": "laughter.mp3"}`.
- Button names come from the file names. To show a nicer name, add it to `input/labels.json`, for example `{"southindian.mp3": "South Indian"}`.

## Try it on a computer

```bash
python -m http.server 8765
```

Then open http://localhost:8765.
