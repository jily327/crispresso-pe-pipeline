# Practical UX qualification — in progress

Base: `72e0f86a495e079cab2ae50d2796e7a3423c78af`.
Branch: `feat/practical-ux-inputs`. Package: 0.8.0 → 0.9.0.

The initial durable implementation checkpoint passed 116 focused Python cases,
169 retained GUI/Setup/Run/M11C.2 cases, and 56 frontend cases (zero failures,
errors or skips in those successful runs). A final reader ZIP-part restriction
was additionally checked against all 35 workbook cases plus the version case.
Generated frontend assets pass the existing identity gate.

The source hashes in frozen-core.json prove scientific Python modules outside
GUI and the explicitly frozen GUI execution/jobs/worker/recovery models remain
byte-identical to the base. Full source/wheel, browser and real native-Core
transport-parity qualification are still pending. This is not an audit pass.

Transient development findings were test harness/expectation defects: the first
20-sample spreadsheet used non-catalog letters; a mocked download returned no
Promise; and a retained denominator-label assertion needed its new explicit
Denominator prefix. No scientific rule was changed to satisfy those tests.
