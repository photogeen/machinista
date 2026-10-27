# Third-party protocol reference

The segmented display header in tools/mikro_feedback.py follows the Ctlra
Mikro MK2 implementation, experimentally confirmed on our Mikro MK1.
No Ctlra library is linked. Reference commit:
`8b6cf95712c0e67c92b93fa270c3ee094f870d28`.

Source: https://github.com/openAVproductions/openAV-Ctlra/blob/8b6cf95712c0e67c92b93fa270c3ee094f870d28/ctlra/devices/ni_maschine_mikro_mk2.c

Copyright and license notice retained below:

```text
/*
 * Copyright (c) 2016, OpenAV Productions,
 * Harry van Haaren <harryhaaren@gmail.com>
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are
 * met:
 *
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 * 3. Neither the name of the copyright holder nor the names of its
 *    contributors may be used to endorse or promote products derived from
 *    this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
 * IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED
 * TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
 * PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
 * HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
 * SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED
 * TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
 * PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
 * LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
 * NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
 * SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
*/
```


## Maschine MK2 protocol reference: cabl

https://github.com/shaduzlabs/cabl — src/devices/ni/MaschineMK2 and src/gfx/displays/GDisplayMaschineMK2. Protocol/control index tables informed the independent Machinist MK2 driver.

The MIT License (MIT)

Copyright (c) 2015 Vincenzo Pacella

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.


## FFmpeg (MP3 import)

Machinista invokes the distribution-provided FFmpeg executable to decode MP3
audio. It is installed as an operating-system package, not as an LV2 effect.
The installed package's copyright and license texts are available in
`/usr/share/doc/ffmpeg/copyright`; package versions and repository sources are
recorded in each image's package/source manifests.

## Rubber Band command-line tools (Sampling STRETCH)

Machinista invokes the distribution-provided `rubberband` executable for sample
time stretching and pitch shifting. The image recipe installs `rubberband-cli`.
The Debian package identifies its main upstream sources as GPL-2-or-later;
the complete notices and component licenses are retained at
`/usr/share/doc/rubberband-cli/copyright`. Package versions and repository
sources are recorded in the image's package/source manifests.

## MK3 protocol references and color display fonts

The original Python MK3 implementation uses descriptor/protocol facts checked
against the attached hardware and the public hardware map at
https://github.com/autotel/maschine-mk3-linux. No implementation from that
GPL-3.0 repository is linked or copied into the driver.

DejaVu Sans regular and bold are distributed in `assets/fonts` for consistent
native color display typography. Their complete upstream copyright and
redistribution terms are retained in `assets/fonts/LICENSE-DejaVu.txt`.
Pillow is provided by the distribution's `python3-pil` package; its notices
remain in `/usr/share/doc/python3-pil/copyright` in the image.
