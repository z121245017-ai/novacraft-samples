Calendar import acceptance sample

Three independent iCalendar files contain fictitious, 30-minute weekly meetings at 09:00 in America/New_York. Each includes its own VTIMEZONE. No account, invitations or personal data are involved.

Try each file separately in an isolated test calendar or your importer. Expand the recurrence over 2026. Sort the resulting occurrences by start time, convert both endpoints to UTC, and compare with expected.json. A match requires the same number, starts and ends. The files overlap in time and intentionally have distinct UIDs.

spring-weekly.ics       Spring daylight saving transition, 3 occurrences.
autumn-weekly.ics       Autumn transition, 3 occurrences.
spring-skip-one.ics     One EXDATE removes March 9 without appending a new week, 2 occurrences.

纽约本地时间每周一 09:00。春季和秋季各有三次，跳过单次的文件只剩两次。请在测试日历分别导入，按 UTC 起止时间和实例数对照 expected.json。适用范围是这三个示例。可自行用于内部评估。
