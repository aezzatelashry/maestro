# Privacy · الخصوصية

<table>
<tr>
<th width="50%">English</th>
<th width="50%" dir="rtl">العربية</th>
</tr>
<tr>
<td valign="top">

**Maestro (elashry-maestro) collects no data.**

- The plugin is a set of Markdown instructions plus three small local Python scripts that Claude Code runs as hooks (since 2.3.0). It has no server, no MCP connector, no network calls and no telemetry. The scripts make no network calls and send nothing.
- Nothing is sent to the author or to any third party.
- It writes only to your own machine:
  - `~/.claude/maestro/` (`rules.md`, `lessons.md`, `runs.md`): your settings, lessons and run log;
  - `~/.claude/maestro/ledger.jsonl`: one line per subagent run, in any project while the plugin is enabled. Each line has the time, the project folder name, the model, the agent type, token counts and, by default, the first 80 characters of the agent's prompt. Also `state.json` and `hooks.log` in the same folder;
  - files inside the project you are working on, such as plans and `docs/STATUS.md`.
- The scripts read the agent's transcript file that Claude Code already keeps on your machine, to count tokens.
- `scripts/inventory.py` only reads the local Claude configuration (installed skills, plugins and hooks) and prints to the terminal. It writes nothing and sends nothing.
- If you set up the live dashboard, the model syncs ledger rows to it through the Claude artifact tool. The scripts themselves never touch the network.
- To stop storing the prompt text, put `{"log_task_text": false}` in `~/.claude/maestro/config.json`. Set `MAESTRO_HOME` to use another folder.
- You can read, edit or delete these files at any time. Uninstalling the plugin does not delete them.
- Claude processes your conversations under Anthropic's own privacy policy, not this one.

Questions: [open an issue](https://github.com/aezzatelashry/maestro/issues).

</td>
<td valign="top" dir="rtl">

**المايسترو (elashry-maestro) ما بيجمعش أي بيانات.**

- الـ plugin عبارة عن تعليمات مكتوبة بـ Markdown، ومعاها 3 سكربتات Python صغيرة على جهازك بيشغّلها Claude Code كـ hooks (من 2.3.0). مالوش سيرفر، ولا MCP connector، ولا بيتصل بالنت، ولا بيبعت أي إحصائيات. السكربتات ما بتتصلش بالنت وما بتبعتش أي حاجة.
- مفيش أي حاجة بتتبعت للمؤلف ولا لأي طرف تالت.
- بيكتب على جهازك إنت بس:
  - `~/.claude/maestro/` (`rules.md` و`lessons.md` و`runs.md`): إعداداتك ودروسك وسجل التشغيل؛
  - `~/.claude/maestro/ledger.jsonl`: سطر لكل تشغيل منفّذ، في أي مشروع طول ما الـ plugin شغّال. كل سطر فيه الوقت، واسم فولدر المشروع، والموديل، ونوع المنفّذ، وأعداد الـ tokens، وبشكل افتراضي أول 80 حرف من طلب المنفّذ. وكمان `state.json` و`hooks.log` في نفس الفولدر؛
  - ملفات جوه المشروع اللي شغال عليه، زي الخطط و`docs/STATUS.md`.
- السكربتات بتقرا ملف محادثة المنفّذ اللي Claude Code بيحتفظ بيه أصلًا على جهازك، عشان تعدّ الـ tokens.
- `scripts/inventory.py` بيقرا إعدادات Claude المحلية بس (المهارات والـ plugins والـ hooks المركّبة) ويطبع على الـ terminal. ما بيكتبش حاجة وما بيبعتش حاجة.
- لو جهّزت اللوحة الحيّة، الموديل هو اللي بيزامن صفوف السجل ليها من خلال أداة الـ artifacts بتاعة Claude. السكربتات نفسها ما بتتصلش بالنت أبدًا.
- عشان توقف تسجيل نص الطلب، حط `{"log_task_text": false}` في `~/.claude/maestro/config.json`. ولو عايز فولدر تاني، اضبط `MAESTRO_HOME`.
- تقدر تقرا الملفات دي أو تعدّلها أو تمسحها في أي وقت. شيل الـ plugin ما بيمسحهاش.
- Claude نفسه بيتعامل مع محادثاتك حسب سياسة الخصوصية بتاعة Anthropic، مش السياسة دي.

للأسئلة: [افتح issue](https://github.com/aezzatelashry/maestro/issues).

</td>
</tr>
</table>
