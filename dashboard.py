import json
import os
import glob
from datetime import date, datetime, timedelta

# ── Config ────────────────────────────────────────────────────────────────────

DATA_WELLNESS  = "data-wellness"
DATA_METRICS   = "data-metrics"
DATA_FITNESS   = "data-fitness"
OUTPUT_FILE    = "dashboard.html"

WEEKLY_SCHEDULE = {
    0: "Circuit training",   # Monday
    1: None,                 # Tuesday
    2: None,                 # Wednesday
    3: "Spin class",         # Thursday
    4: "Swim",               # Friday
    5: None,                 # Saturday
    6: None,                 # Sunday
}

# ── Data loading ──────────────────────────────────────────────────────────────

def load_json_files(folder, pattern="*.json"):
    """Load and combine all JSON files in a folder matching a pattern."""
    records = []
    for filepath in sorted(glob.glob(os.path.join(folder, pattern))):
        with open(filepath) as f:
            data = json.load(f)
            if isinstance(data, list):
                records.extend(data)
            else:
                records.append(data)
    return records

def get_latest_record(records, date_field="calendarDate", target_date=None):
    """Get the most recent record for a given date, or the latest available."""
    if target_date is None:
        target_date = date.today().isoformat()
    
    # Try exact date match first
    matches = [r for r in records if r.get(date_field, "").startswith(target_date)]
    if matches:
        return matches[-1]
    
    # Fall back to most recent record before target date
    past = [r for r in records if r.get(date_field, "") <= target_date]
    return past[-1] if past else None

def get_records_last_n_days(records, n=7, date_field="calendarDate"):
    """Get all records from the last n days."""
    cutoff = (date.today() - timedelta(days=n)).isoformat()
    return [r for r in records if r.get(date_field, "") >= cutoff]

# ── Readiness scoring ─────────────────────────────────────────────────────────

def score_readiness(sleep, training):
    """
    Calculate a readiness score 0-100 from sleep and training data.
    Returns (score, factors) where factors explains the score.
    """
    score = 100
    factors = []

    # Sleep score component (max 40 points impact)
    if sleep:
        overall = sleep.get("sleepScores", {}).get("overallScore", 75)
        if overall >= 80:
            factors.append(("Sleep", f"{overall}/100", "+"))
        elif overall >= 65:
            score -= 15
            factors.append(("Sleep", f"{overall}/100", "~"))
        else:
            score -= 30
            factors.append(("Sleep", f"{overall}/100", "-"))

        # Deep sleep specifically
        deep_seconds = sleep.get("deepSleepSeconds", 0)
        deep_mins = deep_seconds // 60
        if deep_mins < 45:
            score -= 10
            factors.append(("Deep sleep", f"{deep_mins} min", "-"))
        else:
            factors.append(("Deep sleep", f"{deep_mins} min", "+"))

    # Training load component (max 40 points impact)
    if training:
        status = training.get("trainingStatus", "UNKNOWN")
        trend = training.get("fitnessLevelTrend", "UNKNOWN")
        load = training.get("weeklyTrainingLoadSum", 0)
        load_min = training.get("loadTunnelMin", 0)
        load_max = training.get("loadTunnelMax", 9999)

        if status == "OVERREACHING":
            score -= 35
            factors.append(("Training load", "Overreaching", "-"))
        elif status == "RECOVERY":
            score -= 20
            factors.append(("Training load", "Recovery needed", "~"))
        elif status == "PRODUCTIVE":
            factors.append(("Training load", "Productive", "+"))
        elif status == "MAINTAINING":
            factors.append(("Training load", "Maintaining", "~"))
        else:
            factors.append(("Training load", status.title(), "~"))

        if load > load_max:
            score -= 15
            factors.append(("Weekly load", f"{load} (above range)", "-"))
        elif load < load_min:
            factors.append(("Weekly load", f"{load} (below range)", "~"))
        else:
            factors.append(("Weekly load", f"{load} (in range)", "+"))

    # Clamp score to 0-100
    score = max(0, min(100, score))
    return score, factors

def readiness_label(score):
    if score >= 75:
        return "GO FOR IT", "#1D9E75"
    elif score >= 50:
        return "TRAIN BUT MODIFY", "#EF9F27"
    else:
        return "REST DAY", "#E24B4A"

# ── HTML generation ───────────────────────────────────────────────────────────

def format_duration(seconds):
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f"{h}h {m:02d}m"

def generate_html(sleep, training, vo2max):
    today = date.today()
    day_name = today.strftime("%A")
    date_str = today.strftime("%-d %B %Y")
    weekday = today.weekday()
    planned_session = WEEKLY_SCHEDULE.get(weekday)

    score, factors = score_readiness(sleep, training)
    label, label_color = readiness_label(score)

    # Sleep details
    if sleep:
        sleep_scores = sleep.get("sleepScores", {})
        overall_sleep = sleep_scores.get("overallScore", "—")
        deep_mins = sleep.get("deepSleepSeconds", 0) // 60
        rem_mins = sleep.get("remSleepSeconds", 0) // 60
        light_mins = sleep.get("lightSleepSeconds", 0) // 60
        awake_mins = sleep.get("awakeSleepSeconds", 0) // 60
        total_secs = (sleep.get("deepSleepSeconds", 0) +
                      sleep.get("lightSleepSeconds", 0) +
                      sleep.get("remSleepSeconds", 0))
        total_dur = format_duration(total_secs)
        respiration = sleep.get("averageRespiration", "—")
        feedback = sleep_scores.get("feedback", "").replace("_", " ").title()
        insight = sleep_scores.get("insight", "").replace("_", " ").title()
        
        # Bedtime
        start = sleep.get("sleepStartTimestampGMT", "")
        if start:
            dt = datetime.fromisoformat(start)
            bedtime_str = dt.strftime("%-I:%M %p")
        else:
            bedtime_str = "—"
    else:
        overall_sleep = deep_mins = rem_mins = light_mins = "—"
        total_dur = bedtime_str = feedback = insight = "—"
        awake_mins = respiration = 0

    # Training details
    if training:
        train_status = training.get("trainingStatus", "—").title()
        fitness_trend = training.get("fitnessLevelTrend", "—").replace("_", " ").title()
        weekly_load = training.get("weeklyTrainingLoadSum", "—")
        load_min = training.get("loadTunnelMin", "—")
        load_max = training.get("loadTunnelMax", "—")
        feedback_phrase = training.get(
            "trainingStatusFeedbackPhrase", ""
        ).replace("_", " ").title()
    else:
        train_status = fitness_trend = weekly_load = "—"
        load_min = load_max = feedback_phrase = "—"

    # VO2max
    vo2 = vo2max.get("vo2MaxValue", "—") if vo2max else "—"

    # Weekly schedule display
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    schedule_html = ""
    for i, day in enumerate(days):
        session = WEEKLY_SCHEDULE.get(i)
        is_today = (i == weekday)
        border = "border: 2px solid #378ADD;" if is_today else "border: 0.5px solid #ddd;"
        bg = "#E6F1FB" if is_today else "#f9f9f9"
        label_text = session if session else "—"
        schedule_html += f"""
        <div style="text-align:center; padding: 8px 4px; border-radius: 8px; 
                    {border} background: {bg}; font-size: 12px;">
            <div style="color: #888; margin-bottom: 4px;">{day}</div>
            <div style="font-weight: 500; color: #333; font-size: 11px;">
                {label_text}
            </div>
        </div>"""

    # Factors table
    factors_html = ""
    for name, value, direction in factors:
        icon = "✓" if direction == "+" else ("~" if direction == "~" else "↓")
        color = "#1D9E75" if direction == "+" else (
            "#EF9F27" if direction == "~" else "#E24B4A")
        factors_html += f"""
        <tr>
            <td style="padding: 6px 0; color: #666; font-size: 13px;">{name}</td>
            <td style="padding: 6px 0; font-size: 13px; font-weight: 500;">{value}</td>
            <td style="padding: 6px 0; color: {color}; font-size: 14px; 
                       text-align: right;">{icon}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Morning Readiness — {date_str}</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #f5f5f5;
    margin: 0;
    padding: 20px;
    color: #333;
  }}
  .container {{
    max-width: 600px;
    margin: 0 auto;
  }}
  .card {{
    background: white;
    border-radius: 12px;
    border: 0.5px solid #e0e0e0;
    padding: 20px 24px;
    margin-bottom: 12px;
  }}
  .label {{
    font-size: 11px;
    font-weight: 500;
    color: #999;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 6px;
  }}
  .readiness-score {{
    font-size: 64px;
    font-weight: 300;
    line-height: 1;
    color: {label_color};
  }}
  .readiness-label {{
    font-size: 18px;
    font-weight: 500;
    color: {label_color};
    margin-top: 4px;
  }}
  .section-title {{
    font-size: 12px;
    font-weight: 500;
    color: #999;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin: 0 0 12px;
  }}
  .metric-row {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 16px;
  }}
  .metric {{
    background: #f9f9f9;
    border-radius: 8px;
    padding: 10px 12px;
  }}
  .metric-label {{
    font-size: 11px;
    color: #999;
    margin-bottom: 4px;
  }}
  .metric-value {{
    font-size: 18px;
    font-weight: 500;
    color: #333;
  }}
  .metric-sub {{
    font-size: 11px;
    color: #aaa;
    margin-top: 2px;
  }}
  .schedule-grid {{
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 6px;
  }}
  .insight-box {{
    background: #f9f9f9;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 13px;
    color: #555;
    margin-top: 10px;
    line-height: 1.5;
  }}
  .greeting {{
    font-size: 22px;
    font-weight: 500;
    color: #333;
    margin-bottom: 2px;
  }}
  .date-str {{
    font-size: 14px;
    color: #999;
    margin-bottom: 0;
  }}
</style>
</head>
<body>
<div class="container">

  <!-- Header -->
  <div class="card">
    <p class="greeting">Good morning, Kev</p>
    <p class="date-str">{day_name}, {date_str}</p>
  </div>

  <!-- Readiness -->
  <div class="card">
    <div class="label">Readiness</div>
    <div class="readiness-score">{score}</div>
    <div class="readiness-label">{label}</div>
    {"<div class='insight-box'>Today: " + planned_session + "</div>" 
     if planned_session else 
     "<div class='insight-box' style='color:#aaa;'>Rest day — no session planned</div>"}
    <table style="width:100%; margin-top: 16px; border-collapse: collapse;">
      {factors_html}
    </table>
  </div>

  <!-- Sleep -->
  <div class="card">
    <div class="section-title">Last night's sleep</div>
    <div class="metric-row">
      <div class="metric">
        <div class="metric-label">Duration</div>
        <div class="metric-value" style="font-size:16px;">{total_dur}</div>
      </div>
      <div class="metric">
        <div class="metric-label">Score</div>
        <div class="metric-value">{overall_sleep}</div>
      </div>
      <div class="metric">
        <div class="metric-label">Deep</div>
        <div class="metric-value">{deep_mins}m</div>
      </div>
      <div class="metric">
        <div class="metric-label">REM</div>
        <div class="metric-value">{rem_mins}m</div>
      </div>
    </div>
    <div class="metric-row">
      <div class="metric">
        <div class="metric-label">Light</div>
        <div class="metric-value">{light_mins}m</div>
      </div>
      <div class="metric">
        <div class="metric-label">Awake</div>
        <div class="metric-value">{awake_mins}m</div>
      </div>
      <div class="metric">
        <div class="metric-label">Resp rate</div>
        <div class="metric-value" style="font-size:16px;">{round(respiration, 1) if isinstance(respiration, float) else respiration}</div>
        <div class="metric-sub">breaths/min</div>
      </div>
      <div class="metric">
        <div class="metric-label">Bedtime</div>
        <div class="metric-value" style="font-size:14px;">{bedtime_str}</div>
      </div>
    </div>
    {f'<div class="insight-box">{feedback} · {insight}</div>' 
     if feedback and feedback != "—" else ""}
  </div>

  <!-- Training -->
  <div class="card">
    <div class="section-title">Training status</div>
    <div class="metric-row">
      <div class="metric">
        <div class="metric-label">Status</div>
        <div class="metric-value" style="font-size:14px;">{train_status}</div>
      </div>
      <div class="metric">
        <div class="metric-label">Fitness</div>
        <div class="metric-value" style="font-size:14px;">{fitness_trend}</div>
      </div>
      <div class="metric">
        <div class="metric-label">Weekly load</div>
        <div class="metric-value">{weekly_load}</div>
        <div class="metric-sub">{load_min}–{load_max} range</div>
      </div>
      <div class="metric">
        <div class="metric-label">VO2max</div>
        <div class="metric-value">{vo2}</div>
      </div>
    </div>
    {f'<div class="insight-box">{feedback_phrase}</div>' 
     if feedback_phrase and feedback_phrase != "—" else ""}
  </div>

  <!-- Weekly schedule -->
  <div class="card">
    <div class="section-title">This week</div>
    <div class="schedule-grid">
      {schedule_html}
    </div>
  </div>

  <!-- Footer -->
  <p style="text-align:center; font-size:11px; color:#ccc; margin-top: 8px;">
    Generated {datetime.now().strftime("%-I:%M %p")} · 
    Data from Garmin export
  </p>

</div>
</body>
</html>"""

    return html

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    print(f"Building dashboard for {today}...")

    # Load all data
    print("Loading sleep data...")
    sleep_records = load_json_files(DATA_WELLNESS, "*sleepData*.json")
    
    print("Loading training data...")
    training_records = load_json_files(DATA_METRICS, "TrainingHistory*.json")
    
    print("Loading VO2max data...")
    vo2_records = load_json_files(DATA_METRICS, "MetricsMaxMetData*.json")

    # Get latest records
    # Sleep: use yesterday's night (last night)
    sleep = get_latest_record(sleep_records, "calendarDate", yesterday)
    training = get_latest_record(training_records, "calendarDate", today)
    vo2max = get_latest_record(vo2_records, "calendarDate", today)

    print(f"  Sleep record: {sleep.get('calendarDate') if sleep else 'none found'}")
    print(f"  Training record: {training.get('calendarDate') if training else 'none found'}")
    print(f"  VO2max record: {vo2max.get('calendarDate') if vo2max else 'none found'}")

    # Generate dashboard
    print("Generating dashboard...")
    html = generate_html(sleep, training, vo2max)

    # Write file
    with open(OUTPUT_FILE, "w") as f:
        f.write(html)

    print(f"Dashboard written to {OUTPUT_FILE}")
    
    # Open in browser
    os.system(f"open {OUTPUT_FILE}")
    print("Opening in browser...")

if __name__ == "__main__":
    main()