# Controller Lab

Help add support for another controller without installing a test app.

**Open [Controller Lab](https://photogeen.github.io/machinista/controller-survey/) in desktop Chrome or Edge.** Connect the controller to that computer by USB. A controller connected to a Pi is not reachable from a browser running on a different computer.

## For testers

1. Close music applications using the controller. Choose its exact model in Controller Lab.
2. For keyboards, **Quick mapping · 3 keys** is the default: play the lowest key, highest key and first black key from the left (second physical key). This checks MIDI range and note mapping; the other keys are not individually tested. Choose **Full hardware test · every key** before connecting if you want a complete keybed test. Aftertouch remains a separate check. Select **Connect USB controller** and allow access to the NI device. Some devices expose more than one HID interface: use **Add HID interface** if some controls produce no data.
3. Click **Start mapping**. This enables the fixed display test images and the following on-device instructions. For a keyboard the browser may first ask for MIDI permission. A single matching MIDI input is selected automatically; if several ports match, choose the correct input in **MIDI inputs**, then resume.
4. **Displays come first.** Compare the image on each physical display with the browser preview and choose **Matches preview**. The next test image is sent automatically. Each display gets a border/number image, a grid, and colors/brightness. The color-display USB permission is requested once for the guided session. Use **Skip this step** if the display cannot be accessed or its protocol is not implemented; it remains untested or blocked. A successful USB write alone never counts as a visible pass.
5. The control prompts start automatically after the display checks. **Press and release each button once. Turn each encoder clockwise through a few steps, then stop.** There is one step per encoder. Pads and keys must be played and released. Touch sensors and sliders have their own prompts. For the MK2, the eight upper knobs are read as little-endian counters wrapping at 1000, and MASTER as a 4-bit counter wrapping at 16. The two bytes of one knob are treated as one control. The next control appears automatically after a clear action and a short release/debounce interval. Where a display has passed all three image tests, it also shows the current control, progress and action. The browser remains the fallback if display access fails.
6. Keep all controls released during the brief idle-state check between steps. If the idle state is initially unknown, the assistant may ask you to release and repeat that first control once. Multiple simultaneous inputs, reused signals, excessive noise and long-held controls pause the run instead of guessing. Use **Pause**, **Repeat this step**, **Skip this step** or resume when ready. To investigate an unclear signal, pause and use **Record manually**, then confirm the recording. Manual recording remains available without starting the automatic flow.
7. Compare the complete checklist with the hardware. Use **Missing a physical control?** for any missing control, then tick the layout check. A secondary SHIFT label is not another physical button. After the inputs, identify the illuminated LEDs. You can skip unavailable tests explicitly. The final **CHECK COMPLETE** panel summarizes the results and offers **Download JSON**; the same completion message appears on a tested display. The review section lists every untested required control and display image. Partial reports remain incomplete.
8. **Discord · #controllers** downloads the JSON and opens the [Machinista community](https://discord.gg/3B8mQMyQR). Choose **#controllers** and attach the file there yourself. The invitation currently opens #general first. Alternatively, **Download JSON** saves a private backup and **Prepare email** opens a draft to **machinista@photogeen.com**. **Attach the downloaded file yourself** before sending; a website cannot attach it automatically. Webmail also works.

Progress is saved in this browser when storage is available. Keep a downloaded copy too. **Resume saved JSON** can restore it later. Resume only on the same physical controller, with the same octave, MIDI and transpose settings. If the controller disconnects or the page is hidden, repeat the interrupted test. Do not use demo measurements as hardware evidence.

No serial numbers, USB paths, MIDI port names or host names are included in browser exports. Observations are plain text: do not put personal information in them. Emailing is manual; nothing is automatically uploaded to GitHub. By submitting, testers agree to publication of the measurement file under GPL-3.0-or-later. Downloading a private backup does not require publication consent.

## Models and limits

The model selector includes only controllers still needing integration: Maschine Studio, Mikro MK3; Komplete Kontrol S-Series MK1/MK2/MK3, A25/A49/A61 and M32. Model selection describes the planned checklist, **not existing Machinista support**. Already supported MK1/MK2/MK3, Maschine+, Maschine JAM and Mikro MK1/MK2 are excluded from new surveys. The temporary MK2 workflow-test entry has been removed; historical MK2 measurements remain reviewable. Historical measurement files remain reviewable. Sources are linked per model in the assistant. Physical layouts and report decoding still require tester/maintainer review. Missing controls can be added before submission.

On large monochrome panels the instruction font is doubled and bold. MK2 display lighting is temporarily set to 85%; existing contrast is preserved unless effectively off. Disconnect in the assistant to restore the previous lighting settings. Models without a verified brightness protocol retain their hardware settings. Quick presses with an existing idle baseline are accepted as soon as the new control is armed, including while its display instruction is being transmitted.

The browser records inputs and includes a separate inventory and three-image test for every display on the offered controllers. Studio and S-Series MK2 have two color displays; S-Series MK1 has eight individual OLEDs; Mikro MK3, A-Series and M32 have one OLED each. Kontrol S-Series MK3 has a wide color display but uses a different ODR protocol: its display is included as **blocked / protocol not implemented**, not marked passed.

Known monochrome output uses WebHID and checks the device identity and declared report length before writing. Studio/S-MK2 color output uses WebUSB; choose the same controller in the second permission dialog. Connect only one controller of the same model during this test. Only the known vendor display interface and endpoint are claimed, never audio/MIDI/firmware interfaces. No driver is detached and no USB configuration is changed. On some Mac/Windows/Linux setups the OS or NI service prevents exclusive access. A correct test packet does not guarantee a working physical display until a tester confirms the result.

**USB audio, DIN MIDI sockets and live driver behaviour are not verified.** LED identification now follows the inputs. MK2 tests individually named button lights plus red/green/blue channels of group and pad lights. Other models with known output framing probe individual channels; identify the lit item and its color in the browser. Unverified output protocols (including A-Series/M32 LED output) stay unavailable; no guessed packets are sent. Native buttons often use HID rather than MIDI. Browser/OS permissions or an NI background service may prevent access, and some hardware may need an initialization sequence not yet known. Do not replace system drivers or firmware for this test. Report the failure instead.

Safari and Firefox do not provide the same WebHID access as desktop Chrome/Edge. Linux may require HID device permissions. A web page cannot bypass those restrictions. Only the fixed, model-specific display test packets are sent after enabling display output. Arbitrary HID commands and feature-report writes are not available. The tool does not alter firmware or the installed Machinista project. A successful USB write is saved as sent, not confirmed, until the tester checks the physical picture.

## For maintainers

Browser source: `web/controller-survey/`. Shared hardware inventory: `app/controller_survey_catalog.py`; regenerate the browser copy with `python3 tools/build_controller_survey_catalog.py`. Discord link: `web/controller-survey/config.json` → `discordUrl`. Public email address: `web/controller-survey/config.json` → `submissionEmail`. Do not put mail passwords or API keys there. GitHub Pages hosts the site beside the existing manuals.

Review a received file with:

```sh
python3 tools/review_controller_survey.py received-survey.json --output controller-review.json
```

The importer validates identity, limits and raw evidence and derives possible mappings. It never executes a submitted mapping, installs a driver or activates hardware support. Encoder decoding, pad thresholds/crosstalk, LED output and timing need separate implementation and hardware checks. Display observations are preserved with the physical panel, image type, transport, byte count and a SHA-256 digest of the sent bytes. Old reports without display observations remain valid but incomplete. For manual capture, `tester_confirmed` records the tester’s confirmation. Guided capture also sets it after detecting a complete requested action and adds `detection.method: automatic` with the observed signal signature. This still does not independently verify that the tester operated the correctly labelled physical control. No candidate mapping is trusted as a live driver binding. New files use `checklist_version: 3`, one step per encoder, and `keyboard_test: quick` or `full`; older version 2 checklists still test every key and version 1 measurements with two direction steps remain importable. Resuming them in the browser merges the encoder checklist to one step and preserves the original directional evidence under `legacy_controls`. The review file always has `activation_allowed: false`.

Only after checking the file and publication consent, add it under `controller-surveys/<profile-id>/`. These files are evidence, not runtime configuration. Do not include email headers or personal information.

Checks:

```sh
node --test tests/controller-survey/*.test.mjs
python3 -m unittest tests.test_controller_survey
```

## Reference material

Inventories use the controller manufacturers' hardware references, with labels normalized to distinguish physical controls. No manufacturer manual artwork is distributed with this tool.

- [NI manual archive](https://www.native-instruments.com/pages/maschine-downloads)
- [Maschine Studio manual](https://www.native-instruments.com/fileadmin/ni_media/downloads/manuals/maschine_276/MASCHINE_2.0_STUDIO_2.7.6_0518_Manual_English.pdf)
- [Maschine Jam manual](https://www.native-instruments.com/fileadmin/ni_media/downloads/manuals/maschine_278/MASCHINE_JAM_Manual_English_2_7_8.pdf)
- [Mikro MK3 manual](https://www.native-instruments.com/fileadmin/ni_media/downloads/manuals/maschine_2_8/MASCHINE_2.0_MIKRO_MK3_Manual_English_2_8.pdf)
- [Komplete Kontrol S MK1 manual](https://www.native-instruments.com/fileadmin/ni_media/downloads/manuals/komplete_kontrol/KOMPLETE_KONTROL_S-Series_MK1_1.9.2_1217_Manual_English.pdf)
- [Komplete Kontrol S MK2 manual](https://www.native-instruments.com/fileadmin/ni_media/downloads/manuals/komplete_kontrol/KOMPLETE_KONTROL_S-Series_MK2_202_Manual_English.pdf)
- [Kontrol S MK3 keyboard overview](https://docs.native-instruments.com/online-guides/kontrol-s-mk3-manual/en/keyboard-overview.html)
- [A-Series manual](https://www.native-instruments.com/fileadmin/ni_media/downloads/manuals/komplete_kontrol/KOMPLETE_KONTROL_A-Series_Manual_English_04_2022.pdf)
- [M32 manual](https://www.native-instruments.com/fileadmin/ni_media/downloads/manuals/komplete_kontrol/KOMPLETE_KONTROL_M32_Manual_English_28_10_2021.pdf)
- [WebHID browser API](https://developer.chrome.com/docs/capabilities/hid)
- [Web MIDI browser API](https://developer.mozilla.org/en-US/docs/Web/API/Web_MIDI_API)

### Display protocol references

The diagnostic image generator and bounded transport code are original implementations. Packet fields were cross-checked with our existing display encoders and public interoperability notes:

- [Mikro MK3 hardware and display reference](https://github.com/RufusIbiza/Encdr/blob/main/docs/hardware/ni_maschine_mikro_mk3.md)
- [A-Series OLED packet observations](https://gist.github.com/giulioz/7c0d43d97477194a3e18bed37e4e992f)
- [NI display descriptor references](https://github.com/RufusIbiza/Encdr/tree/main/encdr/descriptors)
- [Kontrol S-MK3 ODR research and limitations](https://github.com/tillt/KompleteSynthesia/discussions/29)

S-MK3 rendering requires a separate implementation and real hardware validation. Do not assume the S-MK2 bulk protocol works on S-MK3.
