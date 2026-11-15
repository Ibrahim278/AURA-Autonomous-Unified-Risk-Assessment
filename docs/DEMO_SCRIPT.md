# AURA demo script (about 5 minutes)

Before you start, run the back end and front end, open http://localhost:5173, and make sure
the header says **Lunar surface base** and **Mission day 60**. If you've been clicking
around, switch the header to "ISS" and back to "Lunar surface base" to reset the mission. The tour
restores the demo crew automatically if it was edited.

| Time | On screen | Say |
| --- | --- | --- |
| 0:00 | Header → **▶ Demo tour**, step 1 | "On a Mars mission, help is 20 minutes away by radio. Astronauts have to notice health changes themselves. AURA compares every reading with *their own* preflight baseline and gives a clear Normal, Warning or Critical status." |
| 0:20 | Step 2 (Kenji, day 30) | "Kenji, our flight engineer on a lunar base. A month in, everything is green." |
| 0:35 | Step 3 (day 42, sleep chart) | "Day 42: sleep drops to 5.7 hours against his 7.2 baseline. AURA warns on the *sustained* drop and gives concrete actions." |
| 0:50 | Step 4 (day 48, forecast) | "Here's the clever part: his heart rate is still normal, but AURA's forecast projects the trend and says it will leave his baseline in about a day, with an honest 95% range, and it notices mood falling in step with it." |
| 1:05 | Step 5 (day 50, heart-rate chart) | "Day 50: resting heart rate is 71. Any Earth threshold calls that normal, but it's well above Kenji's own baseline three days running, so AURA catches it." |
| 1:20 | Step 6 → click **Generate daily briefing** | "Claude, acting as an AI flight surgeon, links the chain: sleep, mood, heart, blood pressure. It gives one action per priority. The rule engine always owns the alert level; the AI explains and coaches." |
| 1:45 | Step 7 (Amara, critical) | "Amara has a fever of 39.4 °C from viral reactivation, which spaceflight makes more likely. The immune system lights up red and AURA escalates: contact the flight surgeon now." |
| 2:05 | Step 8 (Amara's symptom log) | "Numbers miss what she feels. She logged chills and growing tiredness, and AURA triages it with fixed rules: chills need follow-up, tiredness three days out of five is persistent. Chest pain or sudden vision loss would mean 'call the ground now'." |
| 2:20 | Step 9 (Message ground) → click **Message ground now**, then **Send** | "One click drafts an urgent message with her status attached. On the Moon it arrives in 1.3 seconds. On a Mars transit it's up to 12 and a half minutes each way, and that's why AURA has to coach her on its own until the flight surgeon's reply comes back." |
| 2:40 | Step 10 (Ortiz, radiation budget) | "Commander Ortiz feels fine and every reading is normal, but she's a veteran. With her earlier missions she's at 85% of NASA's 600 mSv career limit, so AURA warns. A daily dosimeter alone wouldn't show that." |
| 2:55 | Step 11 (Ground view) → click **🖨 Report** on a card | "This is the flight surgeon's side: the whole crew sorted by who needs attention first, and a report they can print or save as PDF." |
| 3:10 | Step 12 → log a check-in, tick a task | "The daily routine is gamified with tasks, streaks and badges, so measuring becomes a habit. A check-in updates the status instantly." |
| 3:25 | Step 13 (real crew data, glucose) | "That mission is synthetic, but AURA also runs on real astronaut data: the Inspiration4 crew's bloodwork from NASA's OSDR. All four had higher glucose the day after landing than just before launch." |
| 3:40 | Step 14 → click **Review C003** | "Claude reviews each real crew member against their own preflight average and suggests what to monitor next flight. AURA's quality check even caught a misaligned row in NASA's published file." |
| 3:55 | Step 15 (crew sidebar) | "It isn't just our demo crew: edit the crew, or import your own CSV and AURA assesses you." |
| 4:05 | Step 16 (Ask AURA, button pulses) → click **✦ Ask AURA**, ask "What should Kenji focus on?", click a button in the answer, then minimise | "And whenever you have a question, Ask AURA is one click away on every screen: answers, steps, and buttons that take you straight there." |
| 4:20 | Step 17 → switch the header to **Mars transit** | "Every indicator maps to NASA's five hazards, and every threshold cites its source. The same tool works on the ISS, a lunar base or a Mars transit." |
| 4:35 | Close the tour | "AURA: personal baselines, transparent alerts, symptom triage and an AI flight surgeon, so astronauts catch problems early and act on their own when Earth is minutes away." |

**Backup if the AI is offline:** the briefing falls back to rule-based mode automatically.
Say "this also works fully offline, which matters with Mars communication delays".
