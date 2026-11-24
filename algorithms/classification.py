
def classify_blocks(
    blocks,
    horizontal_slack,
    vertical_slack,
    hard_blocks=None,
    tolerance=1e-9,
    debug=False,
):
    """
    Classify blocks into the seven SDS subsets.

    I   : Hard blocks
    II  : Both horizontal and vertical slack non-zero
    III : Both horizontal and vertical slack zero
    IV  : Horizontal slack only, width below effective maximum
    V   : Horizontal slack only, width at effective maximum
    VI  : Vertical slack only, height below effective maximum
    VII : Vertical slack only, height at effective maximum
    """

    if hard_blocks is None:
        hard_blocks = set()

    if tolerance < 0:
        raise ValueError("tolerance cannot be negative")

    subsets = {
        "I": [],
        "II": [],
        "III": [],
        "IV": [],
        "V": [],
        "VI": [],
        "VII": [],
    }

    for name in blocks:
        if name not in horizontal_slack:
            raise KeyError(
                f"Horizontal slack missing for block: {name}"
            )

        if name not in vertical_slack:
            raise KeyError(
                f"Vertical slack missing for block: {name}"
            )

    diagnostic_rows = []

    for name, block in blocks.items():
        hs = float(horizontal_slack[name])
        vs = float(vertical_slack[name])

        if hs < -tolerance or vs < -tolerance:
            raise ValueError(
                f"Negative slack detected for {name}: H={hs}, V={vs}"
            )

        if name in hard_blocks:
            subsets["I"].append(name)
            subset = "I"
        else:
            horizontal_nonzero = hs > tolerance
            vertical_nonzero = vs > tolerance

            width_at_max = (
                block.effective_max_width - block.width
            ) <= tolerance * max(
                1.0, abs(block.effective_max_width)
            )

            height_at_max = (
                block.effective_max_height - block.height
            ) <= tolerance * max(
                1.0, abs(block.effective_max_height)
            )

            if horizontal_nonzero and vertical_nonzero:
                subsets["II"].append(name)
                subset = "II"

            elif not horizontal_nonzero and not vertical_nonzero:
                subsets["III"].append(name)
                subset = "III"

            elif horizontal_nonzero:
                if not width_at_max:
                    subsets["IV"].append(name)
                    subset = "IV"
                else:
                    subsets["V"].append(name)
                    subset = "V"

            else:
                if not height_at_max:
                    subsets["VI"].append(name)
                    subset = "VI"
                else:
                    subsets["VII"].append(name)
                    subset = "VII"

        diagnostic_rows.append({
            "name": name,
            "hs": hs,
            "vs": vs,
            "width": block.width,
            "max_width": block.effective_max_width,
            "height": block.height,
            "max_height": block.effective_max_height,
            "subset": subset,
        })

    if debug:
        print("\n========== SLACK CLASSIFICATION DIAGNOSTIC ==========")

        print(
            f"{'Block':<8}"
            f"{'H Slack':>12}"
            f"{'V Slack':>12}"
            f"{'Width':>12}"
            f"{'Eff Max W':>12}"
            f"{'Height':>12}"
            f"{'Eff Max H':>12}"
            f"{'Subset':>10}"
        )

        print("-" * 94)

        for row in diagnostic_rows:
            print(
                f"{row['name']:<8}"
                f"{row['hs']:>12.6f}"
                f"{row['vs']:>12.6f}"
                f"{row['width']:>12.4f}"
                f"{row['max_width']:>12.4f}"
                f"{row['height']:>12.4f}"
                f"{row['max_height']:>12.4f}"
                f"{row['subset']:>10}"
            )

        print("-" * 94)

        print(
            "Subset counts: "
            + ", ".join(
                f"{key}={len(value)}"
                for key, value in subsets.items()
            )
        )

        print(
            "Vertical-only blocks (VI + VII): "
            f"{len(subsets['VI']) + len(subsets['VII'])}"
        )

        print(f"Subset VI shaping candidates: {subsets['VI']}")
        print(f"Subset VII blocks: {subsets['VII']}")

        print("=====================================================\n")

    return subsets
