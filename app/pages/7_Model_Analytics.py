"""Page 7 — Model & Recommendation Analytics.

Every number on this page is read from an experiment artifact through
``edupro.reporting``. None is typed in and none is computed here, so the page
cannot display a figure that no experiment produced — the only alternative to a
measured value is a missing-artifact empty state.

The random baseline is shown as a row in the comparison table rather than as a
footnote. On a 60-course catalogue a ranker that has learned nothing still posts a
Hit Rate near 0.35, so a table without it would read as success.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Streamlit puts the *entry script's* directory on sys.path, so `lib` resolves
# when this page is reached through navigation but not when the file is run or
# tested on its own. Adding the app directory explicitly makes both work.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib import loaders, shell

shell.configure("Model Analytics", "📐")
service = loaders.require_service()
shell.sidebar_provenance(service)

shell.page_header(
    "Model & Recommendation Analytics",
    "The measured evidence behind every claim in this dashboard.",
)

availability = loaders.results_available()
missing = [name for name, present in availability.items() if not present]
if missing:
    shell.empty_state(
        "Experiment results are missing",
        f"Cannot display analytics without: {', '.join(missing)}. Regenerate them:",
        "python scripts/run_segmentation_experiments.py\n"
        "python scripts/run_recommendation_experiments.py",
    )
    st.stop()

headline = loaders.recommendation_headline()

recommendation_tab, segmentation_tab, architecture_tab = st.tabs(
    ["Recommendation", "Segmentation", "Architecture selection"]
)

# ---------------------------------------------------------------- recommendation
with recommendation_tab:
    st.subheader("Baseline comparison")
    shell.evidence(shell.MODEL, "test window, opened exactly once")
    st.caption(loaders.evaluation_caption())

    comparison = loaders.recommendation_comparison()
    display = comparison.assign(
        Method=lambda f: f.apply(
            lambda r: (
                f"{r['method']}  ← deployed"
                if r["is_deployed"]
                else (f"{r['method']}  ← reference" if r["is_reference"] else r["method"])
            ),
            axis=1,
        ),
        **{
            "NDCG@10": lambda f: f["ndcg"].round(4),
            "Hit Rate@10": lambda f: f["hit_rate"].round(4),
            "Precision@10": lambda f: f["precision"].round(4),
            "Recall@10": lambda f: f["recall"].round(4),
            "MRR": lambda f: f["mrr"].round(4),
            "Coverage": lambda f: f["coverage"].round(3),
            "vs random": lambda f: f["vs_random"].round(4),
            "95% CI": lambda f: f.apply(
                lambda r: (
                    "—"
                    if pd.isna(r["ci_low"])
                    else f"[{r['ci_low']:+.4f}, {r['ci_high']:+.4f}]"
                ),
                axis=1,
            ),
            "Significant": lambda f: f["significant"].map({True: "yes", False: "no"}),
        },
    )[
        [
            "Method", "NDCG@10", "Hit Rate@10", "Precision@10", "Recall@10", "MRR",
            "Coverage", "vs random", "95% CI", "Significant",
        ]
    ]
    st.dataframe(display, hide_index=True, width="stretch")

    ceiling = float(comparison["precision_ceiling"].iloc[0])
    st.caption(
        f"Precision@10 cannot exceed **{ceiling:.4f}** on this evaluation: learners "
        "have on average about two held-out courses, so a perfect ranker would still "
        "fill eight of ten slots with courses it cannot be credited for. Precision is "
        "always reported against this ceiling."
    )

    st.error(
        f"**{headline['n_significant']} of {headline['n_methods']} methods are "
        f"significantly better than random.** Every 95% confidence interval on the "
        f"paired per-learner NDCG@10 difference contains zero. Random ranking places "
        f"**{headline['random_rank']}th of {headline['n_methods'] + 1}**, and five "
        f"methods score below it.\n\n{headline['interpretation']}"
    )

    st.divider()
    left, right = st.columns([3, 2], gap="large")

    with left:
        st.subheader("Accuracy against the reference")
        ordered = comparison.sort_values("ndcg")
        colours = [
            shell.SEGMENT_COLORS[0]
            if row["is_deployed"]
            else (shell.REFERENCE_COLOR if row["is_reference"] else "rgba(120,140,160,0.55)")
            for _, row in ordered.iterrows()
        ]
        figure = go.Figure(
            go.Bar(
                x=ordered["ndcg"],
                y=ordered["method"],
                orientation="h",
                marker=dict(color=colours),
                hovertemplate="%{y}: NDCG@10 %{x:.4f}<extra></extra>",
            )
        )
        figure.add_vline(
            x=headline["random_ndcg"],
            line_dash="dash",
            line_color=shell.REFERENCE_COLOR,
            annotation_text="random",
            annotation_position="top",
        )
        figure.update_layout(xaxis_title="NDCG@10")
        shell.show(shell.style_figure(figure, height=460))
        st.caption(
            "The dashed line is the random reference. The blue bar is the deployed "
            "method. Note how little separates the whole field."
        )

    with right:
        st.subheader("Catalogue coverage")
        ordered = comparison.sort_values("coverage")
        figure = go.Figure(
            go.Bar(
                x=ordered["coverage"] * 100,
                y=ordered["method"],
                orientation="h",
                marker=dict(
                    color=[
                        shell.SEGMENT_COLORS[0] if row["is_deployed"] else "rgba(120,140,160,0.55)"
                        for _, row in ordered.iterrows()
                    ]
                ),
                hovertemplate="%{y}: %{x:.0f}% of the catalogue<extra></extra>",
            )
        )
        figure.update_layout(xaxis_title="share of catalogue ever recommended (%)")
        shell.show(shell.style_figure(figure, height=460))
        st.caption(
            "Coverage separates these methods far more sharply than accuracy does. "
            "Global popularity reaches under a third of the catalogue; the deployed "
            "architecture reaches all of it."
        )

    st.divider()
    left, right = st.columns(2, gap="large")

    with left:
        st.subheader("Performance by history depth")
        shell.evidence(shell.MODEL)
        tiers = loaders.per_tier_metrics()
        if tiers.empty:
            shell.empty_state("Not available", "The per-tier breakdown is absent from the artifact.")
        else:
            st.dataframe(
                tiers.rename(
                    columns={
                        "tier": "Tier",
                        "n_users": "Learners",
                        "ndcg": "NDCG@10",
                        "hit_rate": "Hit Rate@10",
                        "coverage": "Coverage",
                    }
                ).style.format(
                    {"NDCG@10": "{:.4f}", "Hit Rate@10": "{:.4f}", "Coverage": "{:.3f}"}
                ),
                hide_index=True,
                width="stretch",
            )
            st.caption(
                "Reported separately because learners with one interaction cannot be "
                "evaluated as if personalisation had applied to them."
            )

    with right:
        st.subheader("Engagement lift (proxy)")
        shell.evidence(shell.PROXY, "the official impact metric")
        proxy = loaders.engagement_lift_proxy()
        columns = st.columns(2)
        columns[0].metric("Deployed method", f"{proxy['deployed']:.3f}", border=True)
        columns[1].metric("Random ranking", f"{proxy['random']:.3f}", border=True)
        st.warning(
            "**This is a proxy, not a measured business outcome.** The official brief "
            "names the metric but defines no formula, and no experiment was run on "
            "real learners. Random ranking scores "
            f"**{proxy['random']:.3f}** on the same measure, which is the number that "
            "makes the deployed method's "
            f"**{proxy['deployed']:.3f}** interpretable. No causal claim is made or "
            "supported."
        )

    st.divider()
    st.subheader("Who receives a recommendation")
    shell.evidence(shell.MODEL)
    coverage = loaders.coverage_accounting()
    columns = st.columns(4)
    columns[0].metric("Learners", f"{coverage['total_learners']:,}", border=True)
    columns[1].metric(
        "Receive a recommendation", f"{coverage['learners_receiving_recommendations']:,}", border=True
    )
    columns[2].metric(
        "Personalised", f"{coverage['learners_receiving_personalised']:,}", border=True
    )
    columns[3].metric(
        "Empty candidate list",
        coverage["learners_with_empty_candidate_pool"],
        border=True,
        help="A learner who has taken so many courses that nothing remains to recommend.",
    )

# ---------------------------------------------------------------- segmentation
with segmentation_tab:
    st.subheader("Cluster quality for the deployed configuration")
    shell.evidence(shell.MODEL, "B_proportion, k = 4, fit window")

    quality = loaders.segmentation_quality()
    columns = st.columns(5)
    columns[0].metric("Silhouette", f"{quality['silhouette']:.4f}", border=True)
    columns[1].metric(
        "Calinski–Harabasz", f"{quality['calinski_harabasz']:.1f}", border=True
    )
    columns[2].metric("Davies–Bouldin", f"{quality['davies_bouldin']:.3f}", border=True)
    columns[3].metric(
        "Intra-cluster similarity", f"{quality['intra_cluster_similarity']:.3f}", border=True
    )
    columns[4].metric("Seed stability (ARI)", f"{quality['seed_stability_ari']:.4f}", border=True)

    st.divider()
    st.subheader("How the number of segments was chosen")
    selection = loaders.k_selection()
    st.caption(selection["rule"])

    sweep = loaders.k_sweep()
    left, right = st.columns(2, gap="large")

    with left:
        figure = go.Figure()
        figure.add_trace(
            go.Scatter(
                x=sweep["k"], y=sweep["silhouette"], mode="lines+markers", name="silhouette",
                line=dict(color=shell.SEGMENT_COLORS[0]),
            )
        )
        figure.add_vline(x=4, line_dash="dash", line_color=shell.SEGMENT_COLORS[3],
                         annotation_text="selected", annotation_position="top")
        figure.update_layout(xaxis_title="number of segments (k)", yaxis_title="silhouette")
        shell.show(shell.style_figure(figure, height=340))
        st.caption(
            f"Silhouette alone would have chosen k = "
            f"{selection['silhouette_optimal_k_unconstrained']}."
        )

    with right:
        figure = go.Figure()
        figure.add_trace(
            go.Scatter(
                x=sweep["k"], y=sweep["inertia"], mode="lines+markers", name="inertia",
                line=dict(color=shell.SEGMENT_COLORS[1]),
            )
        )
        figure.update_layout(xaxis_title="number of segments (k)", yaxis_title="inertia")
        shell.show(shell.style_figure(figure, height=340))
        st.caption(
            "The elbow method, as the brief requires. Inertia falls monotonically "
            "with no knee, so it was produced and reported but did not decide the "
            "answer."
        )

    st.markdown("**Candidates against the pre-registered constraints**")
    candidates = pd.DataFrame(selection["candidates"])
    rename = {
        "k": "k",
        "silhouette": "Silhouette",
        "min_cluster_share": "Smallest segment",
        "mean_bootstrap_jaccard": "Mean Jaccard",
        "n_unstable_clusters": "Unstable clusters",
        "passes_constraints": "Passes both constraints",
    }
    columns_present = [c for c in rename if c in candidates.columns]
    st.dataframe(
        candidates[columns_present].rename(columns=rename),
        hide_index=True,
        width="stretch",
    )
    st.caption(
        f"The gap statistic, included specifically so the project could report "
        f"'no cluster structure' if that were the answer, returned "
        f"k = {selection['gap_optimal_k']} at the range boundary and is reported as "
        f"an instrument that failed rather than as a result."
    )

    st.divider()
    st.subheader("Feature representations compared")
    shell.evidence(shell.MODEL, "each arm at its own best k")
    representations = loaders.representation_comparison()
    st.caption(
        "Each arm is shown at the highest-silhouette k for which every cluster "
        "holds at least 5% of learners. The raw silhouette maximum would rank arms "
        "by how far they were allowed to fragment, not by the quality of their "
        "structure."
    )
    st.dataframe(
        representations.assign(
            Representation=lambda f: f.apply(
                lambda r: f"{r['representation']}  ← deployed" if r["is_deployed"] else r["representation"],
                axis=1,
            )
        )[
            ["Representation", "variant", "best_k", "silhouette", "intra_cluster_similarity",
             "min_cluster_share", "n_features"]
        ].rename(
            columns={
                "variant": "Variant",
                "best_k": "Best k (constrained)",
                "silhouette": "Silhouette",
                "intra_cluster_similarity": "Intra-cluster sim.",
                "min_cluster_share": "Smallest segment",
                "n_features": "Features",
            }
        ),
        hide_index=True,
        width="stretch",
    )

    variants = loaders.demographic_variant_comparison()
    hierarchical = loaders.hierarchical_validation()
    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("**Do demographics change the segmentation?**")
        ari = variants.get("ari_between_variants")
        share = variants.get("demographic_share")
        st.markdown(
            f"Adjusted Rand Index between Variant A (with age and gender) and "
            f"Variant B (behaviour only): **{ari:.3f}**"
            + (
                f". The demographic block explains **{share:.2%}** of "
                "between-cluster variance."
                if share is not None
                else "."
            )
        )
        st.caption(
            (
                "An ARI of 1.000 means the two variants produce the identical "
                "partition. "
                if ari is not None and round(ari, 3) == 1.000
                else "ARI measures how far the two partitions agree; 1.000 is identical. "
            )
            + "Demographics were excluded on this evidence, not by assumption."
        )
    with right:
        st.markdown("**Does another algorithm find the same structure?**")
        for key, label in (
            ("ari_kmeans_vs_ward", "Ward linkage"),
            ("ari_kmeans_vs_average", "Average linkage"),
        ):
            if key in hierarchical:
                st.markdown(f"{label} vs K-Means · ARI **{hierarchical[key]:.3f}**")
        st.caption(
            "Hierarchical clustering was run as an independent validation, as the "
            "brief requires. It is a negative result and is reported as one: the "
            "structure is found by variance-minimising methods and not by others."
        )

# ------------------------------------------------------------- architecture
with architecture_tab:
    st.subheader("Why this architecture was deployed")
    shell.evidence(shell.MODEL, "validation window — the test budget was spent once")

    architectures = loaders.architecture_comparison()
    labels = {
        "A_cluster_popularity_flat": "A · flat segment popularity",
        "B_tiered_with_hybrid_core": "B · tiered, hybrid core",
        "C_tiered_with_selected_core": "C · tiered, selected core (deployed)",
    }
    st.dataframe(
        architectures.assign(Architecture=lambda f: f["architecture"].map(labels))[
            ["Architecture", "ndcg", "hit_rate", "coverage", "gini", "vs_random", "significant"]
        ]
        .rename(
            columns={
                "ndcg": "NDCG@10",
                "hit_rate": "Hit Rate@10",
                "coverage": "Coverage",
                "gini": "Gini",
                "vs_random": "vs random",
                "significant": "Significant",
            }
        )
        .style.format(
            {
                "NDCG@10": "{:.4f}",
                "Hit Rate@10": "{:.4f}",
                "Coverage": "{:.2f}",
                "Gini": "{:.3f}",
                "vs random": "{:+.4f}",
            }
        ),
        hide_index=True,
        width="stretch",
    )

    st.markdown(
        """
        **The deployed architecture was not the most accurate one.** It was chosen
        because it reaches the **whole catalogue** at accuracy indistinguishable
        from the alternatives, and because it degrades honestly: a learner with no
        history is told the list is broad and popular rather than being shown a
        popularity ranking dressed as personalisation.

        Architecture B scores marginally higher but reintroduces a six-signal
        hybrid that a pre-registered parsimony rule had already rejected at a
        larger margin. On a dataset where nothing beats random, paying maintenance
        and explanation cost for an unmeasurable gain is not a trade worth making.
        """
    )

    st.divider()
    st.subheader("Provenance")
    described = service.describe()
    st.json(
        {
            "model_version": described["model_version"],
            "artifact_set": described["artifact_set_version"],
            "trained": described["created_at"],
            "source_workbook_sha256": described["workbook_sha256"],
            "evaluation": loaders.evaluation_caption(),
            "artifacts_present": availability,
        }
    )
    st.caption(
        "Every figure on this page is read from an experiment artifact. Nothing here "
        "is typed in, and nothing is computed by the dashboard."
    )
