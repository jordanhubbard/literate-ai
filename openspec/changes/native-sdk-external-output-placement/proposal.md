# Owned external SDK producer outputs

Framework issue: https://github.com/jordanhubbard/literate-ai/issues/466.

Original native producers such as FreeBSD need unchanged source and independent
object/staging directories. Add an optional live workspace owner to SDK builders,
source services and project acquisition. Preserve the legacy in-source request
and output behavior when no owner is selected. This capability does not admit an
operating-system SDK, consumer, installed product or release by itself.
