# Third-party notices

The root `LICENSE` (Apache-2.0) covers the code in this repository and the
item content we authored; README.md (Licensing) describes the terms for
`runs/`, `paper/`, and `data/judge_scoring_contracts.jsonl`. Each of the 1,632 items in `data/eval.jsonl` records
a source in `metadata.source` and a license label in
`metadata.source_license`. For the 495 items that draw on an upstream project,
the label records the license of the upstream source the item draws on. These
labels are provenance metadata, not a legal conclusion that an item reproduces
copyrightable upstream expression; preserve the attribution and notices the
upstream licenses require.

What the source is depends on the generator. BFCL, TextWorld, tau2-bench, and
the MCPMark trajectory logs supply data or structure that the items adapt.
SymPy, SimPy, OpenSpiel, python-chess, and SciPy, Cantera, RDKit, Astropy, and
Biopython compute the items' observations; one SymPy item also replays a SymPy
doctest.

## License labels

| `metadata.source_license` | Items | Meaning |
|---|---:|---|
| `Apache-2.0` | 1,162 | 955 items from our synthetic recipes (`metadata.source` contains `+synthetic:`), covered by the root `LICENSE`; 203 items that adapt BFCL and 4 whose observations are computed by OpenSpiel, both Apache-2.0 upstream. |
| `MIT` | 250 | Items that adapt TextWorld (194), tau2-bench (36), or the MCPMark trajectory logs (17), and 3 items whose schedules are computed by SimPy. |
| `proprietary-none` | 182 | Items from our own recipes that record no upstream source (`own-workload-code` 69, `own-workload-db` 54, `own-workload-shell` 32, `own-workload-enterprise` 27); despite the label, they are covered by the root Apache-2.0 `LICENSE`. Some observations quote the output of the programs the items were executed against (see [Program output quoted in items](#program-output-quoted-in-items)). |
| `BSD-3-Clause` | 26 | Items whose observations are computed by SymPy; one of them also replays a SymPy doctest. |
| `mixed-permissive-see-contract` | 11 | Laboratory-schedule items. SimPy (MIT) simulates each schedule over measurements computed by SciPy, Cantera, RDKit, and Astropy (BSD-3-Clause) and Biopython (Biopython License Agreement); every one of the 11 items contains measurements from all five libraries. The components are listed below. |
| `GPL-3.0-or-later` | 1 | One item whose observations are computed by python-chess (see [GPL-3.0-or-later item](#gpl-30-or-later-item)). |

In total, 1,137 items come from our own recipes (955 + 182) and record no
upstream source, and 495 draw on an upstream project.

## Upstream projects

Licenses and copyright notices were checked against each project's official
repository or dataset card in September 2026. The copyright notices are under
[Notices](#notices) and the license texts under
[License texts](#license-texts).

| Project | Official URL | License | Items | What the items use | `metadata.source` values |
|---|---|---|---:|---|---|
| BFCL, part of the Gorilla project | https://github.com/ShishirPatil/gorilla | Apache-2.0 | 203 | Adapted: stateful tool classes and their initial configurations | `own-workload-api+seed:ShishirPatil/gorilla (BFCL)` |
| TextWorld | https://github.com/microsoft/TextWorld | MIT | 194 | Adapted: generated text games | `own-workload-game+seed:microsoft/TextWorld` |
| tau2-bench | https://github.com/sierra-research/tau2-bench | MIT | 36 | Adapted: customer-service worlds and tool traces | `own-workload-dialogue+seed:sierra-research/tau2-bench` (35), `harvest-replay-tau2` (1) |
| MCPMark trajectory logs | Hugging Face dataset `Jakumetsu/mcpmark-trajectory-log`, linked as "Trajectory Logs" from https://github.com/eval-sys/mcpmark | MIT (dataset card; the MCPMark benchmark code is Apache-2.0) | 17 | Adapted: operation order of PostgreSQL task trajectories | `own-workload-db+structure-adapted-mcpmark-postgres` (5), `own-workload-db+structure-adapted-mcpmark-postgres-scale` (12) |
| SymPy | https://github.com/sympy/sympy | BSD-3-Clause | 26 | Computes the results of symbolic sessions; one item also replays a SymPy doctest | `own-workload-math+seed:sympy` (25), `harvest-replay-sympy-doctest` (1) |
| SimPy | https://gitlab.com/team-simpy/simpy | MIT | 3 (+11) | Computes discrete-event schedules; also simulates the 11 laboratory schedules | `SimPy` (3), `SimPy+scientific-measurements` (11) |
| OpenSpiel | https://github.com/google-deepmind/open_spiel | Apache-2.0 | 4 | Computes Connect Four and tic-tac-toe states | `OpenSpiel:connect_four+tic_tac_toe` |
| python-chess | https://github.com/niklasf/python-chess | GPL-3.0-or-later | 1 | Computes chess positions, legal-move counts, and check flags; the item's tool description quotes its illegal-move error format | `python-chess` |
| SciPy | https://github.com/scipy/scipy | BSD-3-Clause | 11 | Computes measurements in the laboratory schedules | `SimPy+scientific-measurements` |
| Cantera | https://github.com/Cantera/cantera | BSD-3-Clause | 11 | Computes measurements in the laboratory schedules | `SimPy+scientific-measurements` |
| RDKit | https://github.com/rdkit/rdkit | BSD-3-Clause | 11 | Computes measurements in the laboratory schedules | `SimPy+scientific-measurements` |
| Astropy | https://github.com/astropy/astropy | BSD-3-Clause | 11 | Computes measurements in the laboratory schedules | `SimPy+scientific-measurements` |
| Biopython | https://github.com/biopython/biopython | Biopython License Agreement (some files are dual-licensed under BSD-3-Clause) | 11 | Computes measurements in the laboratory schedules | `SimPy+scientific-measurements` |

The SciPy, Cantera, RDKit, Astropy, and Biopython rows and the "+11" in the
SimPy row all refer to the same 11 `mixed-permissive-see-contract` items.

## Program output quoted in items

The `proprietary-none` items were recorded by executing actions against real
programs. Their generators do not record these execution backends in
`metadata.source`. Where an observation quotes a program's output, such as an
error message or a test summary, the recorded output is included as an
observation of that program's behavior. The programs whose output the items
quote are:

| Program | License | Official URL | Used by | Example of quoted output |
|---|---|---|---|---|
| Odoo 17 Community | LGPL-3.0 | https://github.com/odoo/odoo | enterprise items (`own-workload-enterprise`) | `Record does not exist or has been deleted.` |
| BusyBox on Alpine Linux | GPL-2.0 | https://busybox.net/ | shell items (`own-workload-shell`) | `cat: can't open '...': No such file or directory` |
| CPython | PSF-2.0 | https://www.python.org/ | code items (`own-workload-code`) | `ModuleNotFoundError: No module named '...'` |
| pytest | MIT | https://pytest.org/ | code items (`own-workload-code`) | `1 failed, 3 passed` |
| Git | GPL-2.0 | https://git-scm.com/ | code items (`own-workload-code`) | `fatal: path '...' does not exist in 'HEAD'` |
| SQLite | public domain | https://sqlite.org/ | db items (`own-workload-db`) | `FOREIGN KEY constraint failed` |

## Notices

The upstream projects give the following copyright notices, quoted from their
license files.

TextWorld:

```text
Copyright (c) Microsoft Corporation
All rights reserved.
```

tau2-bench:

```text
Copyright (c) 2025 Sierra Research
```

SymPy:

```text
Copyright (c) 2006-2023 SymPy Development Team

All rights reserved.
```

SimPy:

```text
Copyright (c) 2013 Ontje Lünsdorf and Stefan Scherfke (also see AUTHORS.txt)
```

SciPy:

```text
Copyright (c) 2001-2002 Enthought, Inc. 2003, SciPy Developers.
All rights reserved.
```

Cantera:

```text
Copyright (c) 2001-2009, California Institute of Technology
All rights reserved.

Copyright (c) 2009 Sandia Corporation. Under the terms of
Contract AC04-94AL85000 with Sandia Corporation, the U.S. Government
retains certain rights in this software.

Copyright (c) 2011-2026, Cantera Developers.
All rights reserved.
```

RDKit:

```text
Copyright (c) 2006-2015, Rational Discovery LLC, Greg Landrum, and Julie Penzotti and others
All rights reserved.
```

Astropy:

```text
Copyright (c) 2011-2026, Astropy Developers

All rights reserved.
```

Biopython:

```text
Copyright (c) 1999-2025, The Biopython Contributors
All rights reserved.
```

These sources give no copyright line:

- BFCL (Gorilla) and OpenSpiel: each repository's `LICENSE` is the unmodified
  Apache-2.0 text, and neither repository has a `NOTICE` file. The Apache-2.0
  text is this repository's root `LICENSE`.
- MCPMark trajectory logs: the dataset card declares MIT and gives no
  copyright line.
- python-chess: its `LICENSE.txt` is the GPL-3.0 text, and its README states
  "GPL 3 (or any later version at your option)". The library's author is
  Niklas Fiekas.

## License texts

### MIT License

Used by TextWorld, tau2-bench, SimPy, and the MCPMark trajectory logs.
TextWorld's copy differs only in its quotation marks.

```text
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
```

### BSD 3-Clause License

Used by SymPy, SciPy, Cantera, RDKit, and Astropy, and offered by Biopython
for its dual-licensed files. The text below is RDKit's and Biopython's. The
other copies differ only in naming: clause 3 names SymPy, "the California
Institute of Technology, Sandia Corporation" (Cantera), or "the Astropy Team"
in place of "the copyright holder", and the disclaimer's second sentence names
"THE COPYRIGHT OWNER" (SciPy, Cantera) or "THE REGENTS" (SymPy) in place of
"THE COPYRIGHT HOLDER".

```text
Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice,
   this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors
   may be used to endorse or promote products derived from this software
   without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

### Biopython License Agreement

```text
Permission to use, copy, modify, and distribute this software and its
documentation with or without modifications and for any purpose and
without fee is hereby granted, provided that any copyright notices
appear in all copies and that both those copyright notices and this
permission notice appear in supporting documentation, and that the
names of the contributors or copyright holders not be used in
advertising or publicity pertaining to distribution of the software
without specific prior permission.

THE CONTRIBUTORS AND COPYRIGHT HOLDERS OF THIS SOFTWARE DISCLAIM ALL
WARRANTIES WITH REGARD TO THIS SOFTWARE, INCLUDING ALL IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS, IN NO EVENT SHALL THE
CONTRIBUTORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY SPECIAL, INDIRECT
OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS
OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE
OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE
OR PERFORMANCE OF THIS SOFTWARE.
```

### Apache License 2.0 and GNU GPL version 3

The Apache-2.0 text (BFCL, OpenSpiel) is the root `LICENSE`. The full text
of the GNU General Public License, version 3 (python-chess), is
`LICENSES/GPL-3.0.txt`.

## GPL-3.0-or-later item

This item is distributed under GPL-3.0-or-later; the license text is
`LICENSES/GPL-3.0.txt`:

- `csp-chess_parallel_board_reconciliation_audit-injected` (source
  `python-chess`)
