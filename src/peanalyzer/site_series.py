"""Stable identities and display labels for intended-site biological series."""
ARTIFACT = "intended_sites.json"
CONTRACT = "intended-sites-v1.1"
METHODS = {"two_site_q30": "Q30 paired-read contexts", "full_templates": "Exact full-length templates",
           "core_alleles": "CRISPResso aligned alleles"}
OUTCOMES = {"WT": "WT at both sites", "A_only": "Site A only", "B_only": "Site B only",
            "double_edit": "Complete double edit", "any_edit": "Any intended edit",
            "site_A": "Site A edited", "site_B": "Site B edited"}


def measurement_labels(metric_name):
    prefix, method, outcome = metric_name.split(".")
    if prefix != "intended_sites" or method not in METHODS or outcome not in OUTCOMES:
        raise ValueError("Unknown intended-site observation")
    if outcome in ("site_A", "site_B") and method != "full_templates":
        denominator = "Assessed at site " + outcome[-1]
    else:
        denominator = "Jointly assessed at both sites"
    return METHODS[method], OUTCOMES[outcome], denominator
