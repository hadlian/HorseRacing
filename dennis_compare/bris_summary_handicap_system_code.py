"""
BRIS Summary Handicap System
CSV-based scoring model

Input: comma-delimited CSV file with one row per horse.
Recommended columns:

Race
Horse Number
Horse Name
Morning Line
Avg Speed
Distance Speed
Best Speed
Prime Power
Avg Class
Jockey Rating
Trainer Rating
Earnings
Early Pace
Late Pace
BRIS Top Pick

Notes:
- BRIS Top Pick should be TRUE/YES/1 for the BRIS top pick horse, blank/false otherwise.
- Ratings should be numeric whenever possible.
- The underline trigger is applied when the top horse is 2+ points higher than the third horse.
"""

import pandas as pd
from collections import Counter, defaultdict


CATEGORY_WEIGHTS = {
    "Top 3 Average Speeds": ("Avg Speed", 3),
    "Top 3 Distance Speeds": ("Distance Speed", 2),
    "Top 3 Best Speed": ("Best Speed", 2),
    "Top 3 Prime Power": ("Prime Power", 3),
    "Top 3 Average Class": ("Avg Class", 2),
    "Top 3 Jockeys": ("Jockey Rating", 1),
    "Top 3 Trainers": ("Trainer Rating", 1),
    "Top 3 Earnings": ("Earnings", 1),
}


def clean_number(value):
    if pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.replace("$", "").replace(",", "").strip()
        if value == "":
            return None
    try:
        return float(value)
    except ValueError:
        return None


def top_three(df, column):
    temp = df.copy()
    temp[column] = temp[column].apply(clean_number)
    temp = temp.dropna(subset=[column])
    temp = temp.sort_values(column, ascending=False)
    return temp[["Horse Number", column]].head(3).values.tolist()


def format_top_three(label, ranked):
    if not ranked:
        return f"{label}: NA", []

    horse_numbers = [str(int(row[0])) if float(row[0]).is_integer() else str(row[0]) for row in ranked]
    values = [row[1] for row in ranked]

    # Underline top horse if top rating is 2+ points higher than third horse
    if len(values) >= 3 and values[0] - values[2] >= 2:
        horse_numbers[0] = f"__{horse_numbers[0]}__"

    return f"{label}: " + " - ".join(horse_numbers), [str(int(row[0])) if float(row[0]).is_integer() else str(row[0]) for row in ranked]


def get_bris_top_pick(df):
    if "BRIS Top Pick" not in df.columns:
        return "BRIS Top Pick: NA", None

    picks = df[df["BRIS Top Pick"].astype(str).str.upper().isin(["TRUE", "YES", "Y", "1", "TOP"])]
    if picks.empty:
        return "BRIS Top Pick: NA", None

    horse = picks.iloc[0]["Horse Number"]
    horse = str(int(horse)) if float(horse).is_integer() else str(horse)
    return f"BRIS Top Pick: {horse}", horse


def pace_edge(df, column):
    if column not in df.columns:
        return "NA"
    temp = df.copy()
    temp[column] = temp[column].apply(clean_number)
    temp = temp.dropna(subset=[column])
    if temp.empty:
        return "NA"
    horse = temp.sort_values(column, ascending=False).iloc[0]["Horse Number"]
    return str(int(horse)) if float(horse).is_integer() else str(horse)


def morning_line_value(value):
    if pd.isna(value):
        return None
    value = str(value).strip()
    if "/" in value:
        a, b = value.split("/", 1)
        try:
            return float(a) / float(b)
        except ValueError:
            return None
    try:
        return float(value)
    except ValueError:
        return None


def build_race_summary(df):
    lines = []
    appearances = Counter()
    composite = defaultdict(int)
    underlined_horses = set()

    for label, (column, weight) in CATEGORY_WEIGHTS.items():
        if column not in df.columns:
            lines.append(f"{label}: NA")
            continue

        ranked = top_three(df, column)
        line, horses = format_top_three(label, ranked)
        lines.append(line)

        if line.count("__") >= 2:
            top_horse = horses[0]
            underlined_horses.add(top_horse)

        for idx, horse in enumerate(horses):
            appearances[horse] += 1
            points = max(weight - idx, 0)
            composite[horse] += points

    bris_line, bris_pick = get_bris_top_pick(df)
    lines.append(bris_line)
    if bris_pick:
        appearances[bris_pick] += 1
        composite[bris_pick] += 2

    consensus = appearances.most_common()
    consensus_line = "Consensus Leaders: " + " - ".join([f"{h}({c})" for h, c in consensus[:5]]) if consensus else "Consensus Leaders: NA"

    dominant = [h for h, c in consensus if c >= 4 and h in underlined_horses]
    dominant_line = "Dominant: " + " - ".join(dominant) if dominant else "Dominant: NA"

    early = pace_edge(df, "Early Pace")
    late = pace_edge(df, "Late Pace")

    # Overlay Watch: horses in top 5 consensus with morning line >= 6/1
    overlay = []
    if "Morning Line" in df.columns:
        ml_lookup = {
            str(int(row["Horse Number"])) if float(row["Horse Number"]).is_integer() else str(row["Horse Number"]): morning_line_value(row["Morning Line"])
            for _, row in df.iterrows()
        }
        for horse, _count in consensus[:5]:
            odds = ml_lookup.get(horse)
            if odds is not None and odds >= 6:
                overlay.append(horse)

    overlay_line = "Overlay Watch: " + " - ".join(overlay) if overlay else "Overlay Watch: NA"

    sorted_scores = sorted(composite.items(), key=lambda x: x[1], reverse=True)
    a_tier = [h for h, _ in sorted_scores[:1]]
    b_tier = [h for h, _ in sorted_scores[1:4]]
    c_tier = [h for h, _ in sorted_scores[4:7]]

    score_line = "Composite Scores: " + " | ".join([f"{h}={s}" for h, s in sorted_scores])

    lines.extend([
        consensus_line,
        dominant_line,
        f"Early Pace: {early}",
        f"Late Pace: {late}",
        overlay_line,
        "A: " + " - ".join(a_tier) if a_tier else "A: NA",
        "B: " + " - ".join(b_tier) if b_tier else "B: NA",
        "C: " + " - ".join(c_tier) if c_tier else "C: NA",
        score_line,
    ])

    return lines


def run_bris_summary(csv_file, output_file="bris_summary_output.txt"):
    df = pd.read_csv(csv_file)

    required = ["Race", "Horse Number"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    output = []
    for race in sorted(df["Race"].unique()):
        race_df = df[df["Race"] == race].copy()
        output.append(f"Race {race}")
        output.extend(build_race_summary(race_df))
        output.append("")

    text = "\n".join(output)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(text)

    print(text)
    print(f"\nSaved to: {output_file}")


# Example usage:
# run_bris_summary("bris_data.csv")
