"""Bind a private observation witness to its exact originally issued instance.

This cooperative in-process custody check is not a sandbox against arbitrary
Python code in the trusted receiver. It prevents ordinary dataclass replacement,
copying or restoration from retargeting a witness issued by the actual owner.
"""

from __future__ import annotations

import weakref


class ObservationIssuance:
    __slots__ = ("__issuer", "__instance", "__bound")

    def __init__(self, issuer):
        self.__issuer = issuer
        self.__instance = None
        self.__bound = False

    def require_constructor(self, instance, issuer):
        if issuer is not self.__issuer or self.__bound:
            raise TypeError("an original observation issuer is required")

    def bind(self, instance, issuer):
        self.require_constructor(instance, issuer)
        self.__instance = weakref.ref(instance)
        self.__bound = True

    def require_original(self, instance, issuer):
        if (
            issuer is not self.__issuer
            or not self.__bound
            or self.__instance() is not instance
        ):
            raise TypeError("the original observation instance is required")

    def __copy__(self):
        raise TypeError("observation issuances cannot be copied")

    def __deepcopy__(self, memo):
        raise TypeError("observation issuances cannot be copied")

    def __reduce__(self):
        raise TypeError("observation issuances cannot be restored")
