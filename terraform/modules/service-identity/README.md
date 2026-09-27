# service-identity module

Creates one OpenBao policy and one Kubernetes auth role bound to exactly one
ServiceAccount in one namespace. The caller supplies the policy document and
short-lived token settings.