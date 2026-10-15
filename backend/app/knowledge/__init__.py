"""Knowledge layer — shipped-as-code reference data for the Unified Assets Brain.

Industry-agnostic and derived from published standards (ISO, IEEE, FDA, 3GPP)
and physical-world reliability. Nothing here is tied to a specific customer
dataset; a new industry plugs in by extending these tables.

  - identity:   canonical identity concepts + physics-based weights
  - patterns:   regex pattern library per industry
  - industry:   industry detection + pattern-library loading
  - semantics:  field-name -> canonical-concept semantic matching
"""
