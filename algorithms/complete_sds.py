
"""
Complete Slack-Driven Shaping (SDS) pipeline.

Flow:
1. Run the existing Original SDS algorithm.
2. Build updated horizontal and vertical constraint graphs.
3. Check the optimality conditions (Lemmas 2 and 3).
4. If neither lemma is satisfied, run GP on soft intersection blocks.
5. Apply valid GP dimensions and re-check optimality.
6. Return final layout, history and diagnostics.

Based on:
Yan and Chu, ISPD 2012.
"""

from floorplan.packing import (
    calculate_layout,
    build_constraint_graph,
)

from algorithms.original_sds import run_original_sds

from algorithms.optimality import (
    analyze_critical_paths,
    check_optimality_lemmas,
)

from algorithms.geometric_programming import (
    optimize_intersection_blocks,
    apply_gp_dimensions,
)

from floorplan.constraints import get_mib_groups


def _get_hard_blocks(blocks, placement_constraints=None, extra_hard_blocks=None):
    """Collect blocks that must not be independently reshaped."""

    hard_blocks = set(extra_hard_blocks or [])

    if placement_constraints:
        for name, info in placement_constraints.items():
            if info.get("fixed") or info.get("preplaced"):
                hard_blocks.add(name)

        # MIB blocks must retain identical dimensions.
        for group in get_mib_groups(placement_constraints).values():
            hard_blocks.update(group)

    unknown = hard_blocks - set(blocks)

    if unknown:
        raise ValueError(
            f"Unknown hard blocks: {sorted(unknown)}"
        )

    return hard_blocks


def _build_current_graphs(blocks, hcg_edges, vcg_edges):
    """Build graphs using the current block dimensions."""

    horizontal_graph = build_constraint_graph(
        blocks,
        hcg_edges,
        "horizontal",
    )

    vertical_graph = build_constraint_graph(
        blocks,
        vcg_edges,
        "vertical",
    )

    return horizontal_graph, vertical_graph


def run_complete_sds(
    blocks,
    hcg_edges,
    vcg_edges,
    outline_width,
    max_iterations=200,
    beta=1.0,
    tolerance=1e-6,
    placement_constraints=None,
    hard_blocks=None,
    max_gp_iterations=5,
    solver=None,
    verbose=False,
):
    """
    Run Original SDS followed by optimality checking and GP refinement.

    Parameters
    ----------
    blocks:
        Dictionary {block_name: Block}.

    hcg_edges, vcg_edges:
        Horizontal and vertical constraint edges.

    outline_width:
        Fixed outline width.

    max_iterations:
        Maximum iterations for Original SDS.

    beta:
        Vertical slack distribution factor.

    tolerance:
        Numerical tolerance.

    placement_constraints:
        Optional FloorSet placement constraints.

    hard_blocks:
        Additional blocks that must not be reshaped.

    max_gp_iterations:
        Maximum number of GP refinement attempts.

    solver:
        Optional CVXPY solver name.

    verbose:
        Show GP solver output.

    Returns
    -------
    blocks, final_result, history, diagnostics
    """

    if not blocks:
        raise ValueError("Blocks dictionary cannot be empty.")

    if outline_width <= 0:
        raise ValueError("Outline width must be positive.")

    if max_gp_iterations < 0:
        raise ValueError("max_gp_iterations cannot be negative.")

    # --------------------------------------------------
    # 1. Identify hard blocks
    # --------------------------------------------------

    protected_blocks = _get_hard_blocks(
        blocks,
        placement_constraints,
        hard_blocks,
    )

    print("\n========== COMPLETE SDS ==========")
    print("Number of blocks:", len(blocks))
    print("Hard/protected blocks:", len(protected_blocks))

    # --------------------------------------------------
    # 2. Run the existing Original SDS algorithm
    # --------------------------------------------------

    print("\n========== PHASE 1: ORIGINAL SDS ==========")

    blocks, final_result, sds_history = run_original_sds(
        blocks=blocks,
        hcg_edges=hcg_edges,
        vcg_edges=vcg_edges,
        outline_width=outline_width,
        max_iterations=max_iterations,
        beta=beta,
        tolerance=tolerance,
        placement_constraints=placement_constraints,
    )

    history = list(sds_history)

    # --------------------------------------------------
    # 3. Rebuild graphs and check optimality
    # --------------------------------------------------

    diagnostics = {
        "sds_iterations": len(sds_history),
        "gp_attempts": 0,
        "gp_applied": 0,
        "gp_results": [],
        "optimality_checks": [],
        "optimal": False,
        "termination_reason": None,
    }

    print("\n========== PHASE 2: OPTIMALITY CHECK ==========")

    for gp_iteration in range(max_gp_iterations + 1):

        horizontal_graph, vertical_graph = _build_current_graphs(
            blocks,
            hcg_edges,
            vcg_edges,
        )

        analysis = analyze_critical_paths(
            blocks=blocks,
            horizontal_graph=horizontal_graph,
            vertical_graph=vertical_graph,
            hard_blocks=protected_blocks,
            tolerance=tolerance,
        )

        optimality = check_optimality_lemmas(
            blocks=blocks,
            horizontal_graph=horizontal_graph,
            vertical_graph=vertical_graph,
            hard_blocks=protected_blocks,
            tolerance=tolerance,
        )

        diagnostics["optimality_checks"].append(optimality)

        print(f"\nOptimality check {gp_iteration + 1}:")
        print("Soft intersection blocks:",
              analysis["soft_intersection_blocks"])
        print("Soft HCP count:", analysis["soft_hcp_count"])
        print("Soft VCP count:", analysis["soft_vcp_count"])
        print("Hard VCP exists:", analysis["hard_vcp_exists"])
        print("Optimal:", optimality["optimal"])
        print("Reason:", optimality["reason"])

        if optimality["optimal"]:
            diagnostics["optimal"] = True
            diagnostics["termination_reason"] = (
                "Paper optimality condition satisfied."
            )
            break

        if gp_iteration >= max_gp_iterations:
            diagnostics["termination_reason"] = (
                "Maximum GP iterations reached."
            )
            break

        # --------------------------------------------------
        # 4. Run GP on soft intersection blocks only
        # --------------------------------------------------

        soft_intersection_blocks = set(
            analysis["soft_intersection_blocks"]
        )

        if not soft_intersection_blocks:
            diagnostics["termination_reason"] = (
                "No soft intersection blocks available for GP."
            )
            break

        print("\n========== PHASE 3: GEOMETRIC PROGRAMMING ==========")

        diagnostics["gp_attempts"] += 1

        old_height = final_result["height"]

        try:
            gp_result = optimize_intersection_blocks(
                blocks=blocks,
                horizontal_graph=horizontal_graph,
                vertical_graph=vertical_graph,
                outline_width=outline_width,
                intersection_blocks=soft_intersection_blocks,
                hard_blocks=protected_blocks,
                solver=solver,
                verbose=verbose,
            )

        except Exception as exc:
            diagnostics["gp_results"].append({
                "status": "ERROR",
                "error": str(exc),
            })

            diagnostics["termination_reason"] = (
                f"GP failed: {exc}"
            )

            print("GP failed:", exc)
            break

        diagnostics["gp_results"].append(gp_result)

        print("GP status:", gp_result.get("status"))
        print("GP improved:", gp_result.get("improved"))

        # No dimensions were returned or solver did not succeed.
        if not gp_result.get("optimized_dimensions"):
            diagnostics["termination_reason"] = (
                "GP did not return optimized dimensions."
            )
            break

        # --------------------------------------------------
        # 5. Apply GP dimensions
        # --------------------------------------------------

        try:
            apply_gp_dimensions(
                blocks,
                gp_result,
            )

        except Exception as exc:
            diagnostics["termination_reason"] = (
                f"Could not apply GP dimensions: {exc}"
            )

            print("Could not apply GP dimensions:", exc)
            break

        diagnostics["gp_applied"] += 1

        # --------------------------------------------------
        # 6. Recalculate layout after GP
        # --------------------------------------------------

        final_result = calculate_layout(
            blocks,
            hcg_edges,
            vcg_edges,
            outline_width,
        )

        history.append({
            "phase": "GP",
            "iteration": gp_iteration + 1,
            "width": final_result["width"],
            "height": final_result["height"],
            "gp_status": gp_result.get("status"),
            "gp_improved": gp_result.get("improved"),
        })

        print("Width after GP:", final_result["width"])
        print("Height before GP:", old_height)
        print("Height after GP:", final_result["height"])

        # Reject an infeasible result.
        if not final_result["feasible"]:
            raise RuntimeError(
                "GP produced a layout exceeding the outline width."
            )

        # Stop if there was no meaningful improvement.
        if final_result["height"] >= old_height - tolerance:
            diagnostics["termination_reason"] = (
                "GP did not produce a meaningful height improvement."
            )
            break

    # --------------------------------------------------
    # 7. Final layout and diagnostics
    # --------------------------------------------------

    final_result = calculate_layout(
        blocks,
        hcg_edges,
        vcg_edges,
        outline_width,
    )

    diagnostics["final_width"] = final_result["width"]
    diagnostics["final_height"] = final_result["height"]
    diagnostics["feasible"] = final_result["feasible"]

    if diagnostics["termination_reason"] is None:
        diagnostics["termination_reason"] = (
            "Processing completed."
        )

    print("\n========== FINAL RESULT ==========")
    print("Final width:", final_result["width"])
    print("Final height:", final_result["height"])
    print("Width feasible:", final_result["feasible"])
    print("Optimality condition satisfied:", diagnostics["optimal"])
    print("GP attempts:", diagnostics["gp_attempts"])
    print("Termination:", diagnostics["termination_reason"])

    return blocks, final_result, history, diagnostics
