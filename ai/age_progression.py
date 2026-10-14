"""Age-progression integration point.

The current project does not include an age-progression model. Returning the
original photo under an age-progressed filename would mislead case reviewers,
so callers must wait until a real, reviewed model is integrated.
"""


def generate_age_progression(input_image):
    raise NotImplementedError(
        "Age progression is not implemented; no age-progression model is configured."
    )
