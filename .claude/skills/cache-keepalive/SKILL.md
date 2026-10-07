---
name: cache-keepalive
description: Use when the user agrees to keep this session's prompt cache warm while it waits — on the user coming back, or on a long-running shell or subagent. Pings the session every 50 min for up to 16 h so the next real turn reads the cache instead of rewriting the whole context; stops early only after a checkpoint is written.
---

# SKILL: Cache keep-alive

## Why
Claude Code caches the conversation at a **1-hour TTL**, and a cache read refreshes the timer at no
cost. Past an hour of idle the next turn rewrites the entire context at 2× the input price. A ping
reads it instead: 0.025× on Fable 5.1, 0.05× on Opus 5.5, 0.1× on Opus 5 / 4.8.

Measured on the RTLGen sessions (2026-08-26 → 10-07, API-price equivalents): cold resumes after
idle gaps cost ≈ $704 of ≈ $1,637 main-session spend; a 50-min ping capped at 16 h would have saved
≈ $392 on gaps that ended with the user returning and ≈ $115 on gaps that ended with a task
notification. Break-even ping count is (2 − r)/r for read multiplier r: 79 on Fable 5.1, 39 on
Opus 5.5, 19 on Opus 5 — so on Opus 5 / 4.8 a full 16 h run is roughly break-even, not a win.
How a subscription's usage limits weight reads vs writes is unmeasured.

## When to ask
Ask the user **once per session**, in plain words, at whichever comes first:
- the start of the session, once you can see it will be long or large-context work;
- launching a long-running shell (`run_in_background`) or subagent you will wait on;
- the end of a working block where you expect the user to come back to this session.

Example: *"Want me to keep this session's cache warm while you're away? I'd ping every 50 min for
up to 16 h (about $X total at this context size, vs about $Y to rewrite the cache cold)."* Work the
two numbers out from the current context size and the model's prices; do not quote ones you have
not computed. Skip the question for short or small-context sessions, where a cold resume is cheap.
If the user says no, do not ask again this session.

## Arming
Pings are a chain of **one-shot** `CronCreate` jobs, each scheduling the next — not one recurring
job. A recurring job may fire up to 10% of its period late (an hourly job can land at 66 min, past
the TTL) and cron cannot express a 50-min period. A one-shot fires on time.

1. Set the **deadline** = 16 h from now (local time). Remember it.
2. Schedule the first ping 50 min from now, pinned to that minute/hour/day/month,
   `recurring: false`, with this prompt (fill in the deadline):

   `[cache keep-alive ping — deadline <YYYY-MM-DD HH:MM>] Follow the cache-keepalive skill's ping step.`

3. Tell the user it is armed and until when.

## On each ping
Keep the turn tiny: no file reads, no tool calls beyond the ones below, a one-line reply.
1. **Finished?** If the work is done and nothing will resume here — no background task or subagent
   pending, and the user is not expected back to this session — go to *Stopping*.
2. **Deadline passed?** Go to *Stopping*.
3. A real (non-ping) user turn since the last ping resets the deadline to 16 h after that turn.
4. Otherwise schedule the next one-shot 50 min from now with the same prompt (updated deadline)
   and reply `keep-alive ok, next <HH:MM>, deadline <HH:MM>`.

## Stopping
Stopping lets the cache go cold, so the work must be resumable from a **fresh** session first:
1. Write a checkpoint with the `checkpoint` skill (`checkpoint.py write --project <p>`) — this ping
   is the last moment the full context is still cheap to read. Skip only if nothing has happened
   since the last checkpoint.
2. `CronList`, then `CronDelete` any pending keep-alive ping.
3. Reply in one line: stopped, why, and where the checkpoint is.

Stop the same way when the user says to stop. Session-only: cron jobs die with the session, so
exiting Claude Code needs no cleanup.
