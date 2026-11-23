# Maestro · المايسترو

[العربية](#العربية) · [English](#english)

---

<div dir="rtl">

## العربية

**المايسترو** plugin لـ Claude Code: أقوى موديل متاح عندك (Fable، أو Opus لو Fable مش موجود) بيخطط ويوجّه ويراجع، والموديلات الأصغر (Opus وSonnet وHaiku) بتنفّذ. كل مهمة بتروح لأصغر موديل يعملها صح.

الفكرة بسيطة: أغلب شغل التنفيذ ما يحتاجش أغلى موديل، بس المراجعة والقرار محتاجينه. فالمايسترو بيفصل بينهم.

### بيعمل إيه

- **بيحدد حجم الطلب** (صغير، متوسط، كبير أو حساس)، والحجم هو اللي بيقرر الخطوات. التعديل الصغير ما ياخدش خطة كاملة.
- **بيكتب خطة** بجدول مهام: الموديل لكل مهمة، والملفات، والمهارات المطلوبة، والدليل اللي يثبت إنها خلصت.
- **بيختار الموديل حسب نوع الشغل**، وبيضبط الاختيار ده مع الوقت من سجل النتائج الفعلية.
- **بيكتب بريف كامل** لكل منفّذ، لأن المنفّذ ما يعرفش غير اللي في البريف.
- **بيراجع بنفسه.** تقرير المنفّذ مش دليل: المايسترو بيقرا الـ diff ويشغّل الدليل.
- **في الشغل الكبير:** بيكتب تحليل للفشل قبل التنفيذ، وبيبعت الشغل لمراجع مستقل بسياق جديد.
- **عنده حدود للتشغيل:** لو المهمة فشلت بعد رفع الموديل، أو الخطة كبرت أكتر من اللازم، بيوقف ويسألك.
- **بيحفظ الحالة** في `docs/STATUS.md`، عشان أي جلسة جديدة تكمّل من نفس النقطة.
- **بيشتغل على المستندات كمان:** مناقصات، وsubmittals، وتقارير مشاريع، وعروض، وBOQ. كل رقم ليه مصدر، وممنوع اختراع أي حاجة.
- **بيتعلّم:** الدروس والسجل بيتحفظوا عندك في `~/.claude/maestro/`، مش جوه الـ plugin، فما بيضيعوش مع التحديث.

### المتطلبات

- Claude Code، لأنه بيعتمد على أدوات `Agent` و`SendMessage` والـ worktrees.
- يشتغل أحسن لو Fable متاح للتخطيط. من غيره Opus بياخد الدور ده.

### التركيب

جوه Claude Code:

```
/plugin marketplace add aezzatelashry/maestro
/plugin install maestro@maestro
```

### الاستخدام

قول «المايسترو» أو «وزّع الشغل»، أو شغّل الأمر:

```
/maestro:maestro
```

### الملفات

| المسار | فيه إيه |
|---|---|
| `skills/maestro/SKILL.md` | القواعد الأساسية |
| `skills/maestro/references/documents.md` | شغل المستندات |
| `skills/maestro/references/evidence.md` | الدليل لكل نوع مهمة |
| `skills/maestro/references/templates/` | قوالب فاضية للدروس والسجل |
| `examples/` | أمثلة خيالية: خطة لميزة، وخطة لرد على مناقصة، وبريف لمنفّذ، وملف حالة |

### ملفاتك الخاصة

في أول تشغيل، المايسترو بيعمل `~/.claude/maestro/` وفيه:

- **`rules.md`:** تعديلاتك على القيم الافتراضية، زي جدول الموديلات، وحدود التشغيل، ومكان مكتبة المهارات بتاعتك.
- **`lessons.md`:** الدروس اللي اتعلّمها من التشغيلات اللي فاتت.
- **`runs.md`:** سجل المهام والموديلات والنتائج.

الملفات دي عندك إنت بس، وما بتترفعش في أي مكان.

### الترخيص

MIT

</div>

---

## English

**Maestro** is a Claude Code plugin where the strongest model you have (Fable, or Opus when Fable is not available) plans, directs and reviews, while smaller models (Opus, Sonnet, Haiku) do the building. Each task goes to the smallest model that does it well.

Most implementation work does not need the most expensive model; review and judgment do. Maestro separates the two.

The skill itself is written in Egyptian Arabic. Claude reads it the same way in any language, and replies in whatever language your `CLAUDE.md` asks for.

### What it does

- **Sizes the request** (small, medium, large or sensitive), and the size decides which steps run. A small edit does not get a full plan.
- **Writes a plan** as a task table: model, files, skills and the evidence that proves each task is done.
- **Routes by kind of work**, and tunes that routing over time from a log of real outcomes.
- **Writes a complete brief** for every executor, since the executor knows only what the brief says.
- **Reviews the work itself.** An executor's report is not evidence: Maestro reads the diff and runs the evidence.
- **For large work:** writes a pre-mortem before dispatch, and sends the result to an independent reviewer with a fresh context.
- **Has run limits:** if a task still fails after moving to a bigger model, or the plan grows too much, it stops and asks you.
- **Keeps state** in `docs/STATUS.md`, so a new session picks up where the last one stopped.
- **Handles documents too:** tender responses, submittals, project reports, decks and BOQs. Every figure is traced to its source, and nothing is invented.
- **Learns:** lessons and the run log live in `~/.claude/maestro/`, outside the plugin, so updates do not erase them.

### Requirements

- Claude Code, because it relies on the `Agent` and `SendMessage` tools and on worktrees.
- Works best with Fable available for planning. Without it, Opus takes that role.

### Install

Inside Claude Code:

```
/plugin marketplace add aezzatelashry/maestro
/plugin install maestro@maestro
```

### Use

Say "maestro" or «المايسترو», or run:

```
/maestro:maestro
```

### Files

| Path | Contents |
|---|---|
| `skills/maestro/SKILL.md` | Core rules |
| `skills/maestro/references/documents.md` | Document mode |
| `skills/maestro/references/evidence.md` | Evidence for each kind of task |
| `skills/maestro/references/templates/` | Empty templates for lessons and the run log |
| `examples/` | Fictional examples: a feature plan, a tender-response plan, an executor brief and a status file |

### Your private files

On first run Maestro creates `~/.claude/maestro/` with:

- **`rules.md`:** your overrides to the defaults, such as the model table, run limits and where your skill library lives.
- **`lessons.md`:** lessons learned from past runs.
- **`runs.md`:** a log of tasks, models and outcomes.

These files stay on your machine and are never uploaded anywhere.

### License

MIT
