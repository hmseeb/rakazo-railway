#!/usr/bin/env python3
"""Builds the live Rakazo source project in Auromations (the regeneration master).

Literal values rather than cross-service references: a ${{other.VAR}} reference
resolves to an empty string in a live project and only fills in during a
template deploy, so a source project wired with references boots broken.
References go back in during template repair, where they belong.
"""
import pathlib
import secrets
import string
import sys

sys.path.insert(0, str(pathlib.Path("~/.claude/skills/create-template-for-railway/scripts").expanduser()))
import rw  # noqa: E402

WORKSPACE = "fc4796db-2c6c-4354-a564-d4a1d900af53"  # Auromations
IMAGE = "ghcr.io/hmseeb/rakazo-railway:v0.1.6"
PG_IMAGE = "ghcr.io/railwayapp-templates/postgres-ssl:17"


def rand(n=48, alphabet=string.ascii_letters + string.digits):
    return "".join(secrets.choice(alphabet) for _ in range(n))


def q(doc, variables=None, internal=False):
    return rw.gql(doc, variables, internal=internal)


def main():
    project = q(
        """mutation($input: ProjectCreateInput!) {
             projectCreate(input: $input) { id environments { edges { node { id name } } } } }""",
        {"input": {"name": "rakazo-source", "workspaceId": WORKSPACE}},
    )["projectCreate"]
    pid = project["id"]
    env = next(e["node"]["id"] for e in project["environments"]["edges"] if e["node"]["name"] == "production")
    print(f"project {pid}  env {env}")

    pg_password = rand(32)
    database_url = f"postgresql://postgres:{pg_password}@postgres.railway.internal:5432/railway"

    def service(name, image, variables):
        svc = q(
            """mutation($input: ServiceCreateInput!) { serviceCreate(input: $input) { id } }""",
            {"input": {"projectId": pid, "environmentId": env, "name": name,
                       "source": {"image": image}, "variables": variables}},
        )["serviceCreate"]["id"]
        q(
            """mutation($serviceId: String!, $environmentId: String!, $input: ServiceInstanceUpdateInput!) {
                 serviceInstanceUpdate(serviceId: $serviceId, environmentId: $environmentId, input: $input) }""",
            {"serviceId": svc, "environmentId": env,
             "input": {"restartPolicyType": "ON_FAILURE", "restartPolicyMaxRetries": 10}},
        )
        print(f"  service {name} {svc}")
        return svc

    def volume(svc, mount):
        q(
            """mutation($input: VolumeCreateInput!) { volumeCreate(input: $input) { id } }""",
            {"input": {"projectId": pid, "environmentId": env, "serviceId": svc, "mountPath": mount}},
        )

    pg = service("Postgres", PG_IMAGE, {
        "PGDATA": "/var/lib/postgresql/data/pgdata",
        "POSTGRES_USER": "postgres",
        "POSTGRES_PASSWORD": pg_password,
        "POSTGRES_DB": "railway",
        "SSL_CERT_DAYS": "820",
        "RAILWAY_DEPLOYMENT_DRAINING_SECONDS": "60",
    })
    volume(pg, "/var/lib/postgresql/data")

    # Placeholder public-domain literals; corrected after the domain exists,
    # then baked by a fresh deploy (serviceInstanceDeployV2, NOT redeploy).
    app = service("Rakazo", IMAGE, {
        "PORT": "5173",
        "NODE_ENV": "production",
        "DATABASE_URL": database_url,
        "DATA_DIR": "/data",
        "BETTER_AUTH_SECRET": rand(40),
        "ENCRYPTION_KEY": rand(64, "0123456789abcdef"),
        "SCREEN_PROXY_SECRET": rand(40),
        "BETTER_AUTH_URL": "https://PLACEHOLDER",
        "WEB_ORIGIN": "https://PLACEHOLDER",
        "API_URL": "https://PLACEHOLDER",
        "RAKAZO_HOST": "PLACEHOLDER",
        "SIGNUPS_ENABLED": "true",
        "SANDBOX_PROVIDER": "none",
        "PI_DEFAULT_PROVIDER": "openrouter",
    })
    q(
        """mutation($serviceId: String!, $environmentId: String!, $input: ServiceInstanceUpdateInput!) {
             serviceInstanceUpdate(serviceId: $serviceId, environmentId: $environmentId, input: $input) }""",
        {"serviceId": app, "environmentId": env,
         "input": {"healthcheckPath": "/api/auth/capabilities"}},
    )
    volume(app, "/data")
    domain = q(
        """mutation($input: ServiceDomainCreateInput!) { serviceDomainCreate(input: $input) { domain } }""",
        {"input": {"environmentId": env, "serviceId": app, "targetPort": 5173}},
    )["serviceDomainCreate"]["domain"]
    origin = f"https://{domain}"
    print(f"  origin {origin}")

    # Bake the real public origin, then a genuinely fresh deploy picks it up.
    for key, value in {
        "BETTER_AUTH_URL": origin, "WEB_ORIGIN": origin, "API_URL": origin,
        "RAKAZO_HOST": domain,
    }.items():
        q(
            """mutation($input: VariableUpsertInput!) { variableUpsert(input: $input) }""",
            {"input": {"projectId": pid, "environmentId": env, "serviceId": app,
                       "name": key, "value": value}},
        )
    q(
        """mutation($serviceId: String!, $environmentId: String!) {
             serviceInstanceDeployV2(serviceId: $serviceId, environmentId: $environmentId) }""",
        {"serviceId": app, "environmentId": env},
    )
    print()
    print(f"PROJECT={pid}")
    print(f"ENV={env}")
    print(f"PG={pg}")
    print(f"APP={app}")
    print(f"ORIGIN={origin}")


if __name__ == "__main__":
    main()
