# T5B1 hot-air temperature test build

Based on upstream commit 50651a5 (26.9.4-b0), matching the installed version.

BF mode selects pass a dictionary to `set_attributes`. Previously that path
did not bundle the mapping's centralized cooking parameters, although the
number-control path did. Selecting a cooking mode could therefore encode
temperature and duration as FF (unspecified) in the model's Lua protocol.

This build also bundles those parameters when a BF mode is selected. Explicit
command values take precedence, followed by recent values within the existing
five-second window, then device status. No default temperature is invented.
Pause, stop, resume and lock commands remain separate status commands.

Offline regression checks: `python -m unittest discover -s tests -v`.
The T5B1 Lua codec is additionally checked offline against the installed codec;
no commands are sent to the appliance during these checks.

For a supervised appliance test, set a valid desired temperature and duration
first, then select hot air. Selecting a cooking mode can start cooking; changing
a cooking parameter can also resend the current cooking mode. Verify that the
official app reports the requested target temperature and duration. This patch
does not prove physical temperature accuracy or change optimistic HA reporting.

The custom build must not be overwritten by a normal upstream HACS update if
the fix is to remain active. Keep the original integration backup for rollback.
