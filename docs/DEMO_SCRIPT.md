# AURA demo script (about 5 minutes)

**Story in one line:** Kenji's problem is caught early → Amara's emergency reaches the ground despite the signal delay → the same ideas work on real NASA astronaut data.

Before you start, open the app (the live link, or http://localhost:5173 locally). Click **Reset** in the header so the
mission is fresh: **Lunar surface base**, **Mission day 60**. On the free hosting plan, open the link a few minutes
early so the server is awake. The tour restores the demo crew automatically if it was edited.

Each tour step moves to the right page by itself, so you only press **Next**. Keep each line short; the tour card shows the detail.

| Time | On screen | Say |
| --- | --- | --- |
| 0:00 | Home page → **▶ Start the demo tour** (step 1) | "On a Mars mission, help is 20 minutes away by radio, so astronauts have to notice health changes themselves. AURA compares every reading with *their own* preflight baseline and gives a clear Normal, Warning or Critical status, with the reason. AURA: your crew's health, even when Earth is 20 minutes away." |
| 0:20 | Step 2 (Kenji, day 30) | "Kenji, our flight engineer on a lunar base. A month in, everything is green." |
| 0:30 | Step 3 (day 42, sleep) | "Day 42: sleep drops to 5.7 hours against his 7.2 baseline. AURA warns on the *sustained* drop." |
| 0:45 | Step 4 (day 48, forecast) | "His heart rate is still normal, but the forecast projects the trend and says it leaves his baseline in about a day, with an honest 95% range." |
| 1:00 | Step 5 (day 50, heart rate) | "Day 50: 71 bpm. Any Earth threshold calls that normal, but it's well above Kenji's own 64, three days running." |
| 1:10 | Step 6 → click **Generate daily briefing** | "Claude, as an AI flight surgeon, links the chain: sleep, mood, heart, blood pressure. The rules set the alert level; the AI only explains and coaches." |
| 1:30 | Step 7 (Daily plan) | "And it changes his day: steady cycling instead of intervals, a ride after lunch for glucose, a longer sleep window, a call home for his mood. Every change says why." |
| 1:45 | Step 8 (Amara, critical) | "Amara has a fever of 39.4 from viral reactivation. AURA escalates: contact the flight surgeon now." |
| 1:55 | Step 9 (Check-in & symptoms) → click **🎙 Speak** (optional) | "Numbers miss what she feels, so AURA triages symptoms with fixed rules. She can even log readings by voice, hands-free." |
| 2:10 | Step 10 → **Message ground now**, **Send**; switch header to **Mars transit** | "One click drafts an urgent message with her status. From the Moon it arrives in 1.3 seconds. From Mars, up to 12 and a half minutes each way. That gap is why AURA has to coach her on its own." |
| 2:35 | Step 11 (Radiation) | "Commander Ortiz feels fine, but with earlier missions she's at 85% of NASA's career radiation limit. A daily dosimeter wouldn't show that." |
| 2:50 | Step 12 (Ground view) → **🖨 Report** | "The flight surgeon's side: the whole crew sorted by who needs attention first, with a printable report." |
| 3:05 | Step 13 (Team wellbeing) | "Long missions are a team problem. The crew score is 54, and Kenji is lowest because his mood and sleep are far below his normal." |
| 3:15 | Step 14 (Routine & rewards) | "Streaks, badges, weekly challenges and a crew board make measuring a habit." |
| 3:25 | Step 15 (Real NASA data, glucose) | "That mission is synthetic. But AURA also runs on real astronaut data: Inspiration4 bloodwork from NASA's OSDR. All four had higher glucose right after landing." |
| 3:40 | Step 16 (Immune cytokines, IL-6) | "80 immune and cardiac markers from the same crew. IL-6, an inflammation signal, rose after landing in all four. AURA's quality check also caught values stuck at the assay limit and left them out." |
| 3:55 | Step 17 → click **Review C003** | "Claude reviews each real astronaut against their own preflight values and suggests what to monitor next flight." |
| 4:10 | Step 18 → **✦ Ask AURA**, type "take me to radiation", then minimise | "Ask AURA is on every page: answers, steps, and it moves you around the app." |
| 4:25 | Step 19 | "Every indicator maps to NASA's five hazards, and every threshold cites its source. It works on the ISS, a lunar base or a Mars transit, and you can import your own data." |
| 4:40 | Close the tour | "AURA: personal baselines, early warning, transparent rules and an AI flight surgeon, so astronauts can act on their own when Earth is minutes away." |

**If the AI is offline** (no API key): the briefing, reviews and Ask AURA fall back to rule-based answers automatically.
Say "this also works fully offline, which matters with Mars communication delays".

**Short on time?** Skip steps 13, 14 and 17; the story still holds.
