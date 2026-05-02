# MAIA Dashboard Documentation

The MAIA Dashboard is a web-based application that provides a user-friendly interface to interact with the MAIA platform. The dashboard allows users to request project allocations, link their account to a project, and access the project-specific tools and resources.

Additionaly, the MAIA Dashboard is used to manage a number of platform operations, such as user, project, and resource management, as well as monitoring and logging.


## Registration Lifecycle

This section walks through the full path from a new user landing on the dashboard to having a working project namespace. The detailed reference for each admin action lives in the [User Management](#user-management) and [Project Management](#project-management) sections below; this section is the end-to-end map.

> **Prerequisite:** the cluster must already have Keycloak configured with a `MAIA:admin` group containing at least one administrator, a `MAIA:users` group, and SMTP credentials wired into the dashboard. A dedicated "Pre-flight for Registration" section in the Installation guide is planned as a follow-up.

### 1. End user submits the registration form

A new user reaches the registration page (`https://<dashboard-host>/register/`) and submits:

| Field | Notes |
|---|---|
| `email` | Used as both the Keycloak `username` and `email`. |
| `namespace` | Comma-separated list of project IDs the user wants to join. May be empty if the user only wants an account, or may include a project that does not yet exist (in which case it appears as a *Pending* project to admins). |

The submission writes a row into the `maia_user_model` table. **Nothing is created in Keycloak yet** — the user cannot log in until an admin approves them.

### 2. End user (optionally) submits a project request

If the user also needs a brand-new project, they fill out the project request form. The schema is:

| Field | Example | Notes |
|---|---|---|
| `namespace` | `my-project` | Project ID. **Will be lowercased and `_` will be replaced with `-`** before being used as the Kubernetes namespace (e.g. `My_Project` → `my-project`). The Keycloak group is `MAIA:<namespace>`. |
| `email` | `pi@uni.edu` | The project admin's email (becomes the Project Admin tag in the user list). |
| `cpu_limit` | `2` | Per-user CPU request. |
| `memory_limit` | `2 Gi` | Per-user memory request. |
| `date` | `2026-12-31` | Allocation end date. |
| `cluster` | `maia-cluster-name` | Target cluster (must already be registered in the dashboard ConfigMap). |
| `gpu` | `NVIDIA-RTX-A6000` or `N/A` | GPU type, or `N/A` for CPU-only. |
| `minimal_env` | `Minimal` / `Pro` | Determines which sub-applications are deployed (see below). |
| `users` | `[a@x, b@y]` | Initial set of project members. |

The request lands in `maia_project_model` with a *Pending* status and surfaces on both the **Users** and **Projects** admin pages.

### 3. Admin approves the user (Keycloak user creation)

In the **Users** page, the admin clicks the **ID icon** next to the user. This:

1. Calls `register_user_in_keycloak()` (`MAIA/keycloak_utils.py:236`), which creates the Keycloak user with a temporary password (`UPDATE_PASSWORD` is set as a required action on first login).
2. If SMTP is configured (`email_account`, `email_password`, `email_smtp_server` present in the environment or `maia_config.yaml`), sends an **approved-registration email** to the user with their temp password and the dashboard login URL. **If SMTP is not configured the user is created silently and never receives a password** — admins must communicate it out of band.

The ID icon is replaced by a green check mark once the Keycloak user exists.

### 4. Admin approves the project (Keycloak group creation)

In the **Projects** page (or the equivalent column on the Users page), the admin clicks the **group icon** next to the pending project. This calls `register_group_in_keycloak()` and creates a Keycloak group named `MAIA:<namespace>`. No Kubernetes resources exist yet at this point — only the identity grouping.

### 5. Admin links the user to the project

Back on the **Users** page, the **group icon** on a user row calls `register_users_in_group_in_keycloak()`:

- Adds the user to `MAIA:<project_namespace>`.
- **Also** silently adds the user to `MAIA:users` (any error here is swallowed). The `MAIA:users` group must therefore exist in Keycloak — see the pre-flight guide.

To unlink a user later, edit the user's project list in their row and click the unlink icon. The user loses access to the project's Keycloak group, but **resources tied to that user inside the namespace (JupyterHub home dir, allocated SSH port, etc.) are not cleaned up.**

### 6. Admin deploys the project (`deploy` icon)

This is the heaviest step. Clicking **deploy** calls `deploy_maia_toolkit_api()` (`MAIA_scripts/MAIA_install_project_toolkit.py:145`), which renders the project Helm chart and creates an ArgoCD application that materializes:

| Always | When `minimal_env != Minimal` (i.e., "Pro") |
|---|---|
| Kubernetes namespace `<namespace>` | MinIO bucket + console with Keycloak OIDC integration, exposed at `https://<subdomain>.<domain>/minio-console` |
| Shared PVC (10 Gi, ReadWriteMany) on `shared_storage_class` | MLflow instance with encoded credentials |
| Per-user JupyterHub instance (usernames URL-encoded: `@`→`-40`, `.`→`-2e`, `-`→`-2d`) | MySQL database with project-specific user backing MLflow |
| SSH `Service` (LoadBalancer or NodePort, allocated from the cluster's `port_range`) | Optional Orthanc DICOM endpoint |
| Ingress for JupyterHub with the cluster's annotation set (Traefik resolver *or* nginx + cert-manager issuer, depending on `ingress_class`) | |
| ArgoCD `Application` owned by `MAIA:<namespace>` | |
| CIFS mount (enabled by default via `extra_configs.enable_cifs=True`) | |

Once deployment completes, both the group and deploy icons are replaced by an **update** button, which triggers a Helm upgrade / ArgoCD re-sync against the same chart. Use this after editing project resources or chart values.

> **Traefik / Kaapana note:** if MAIA is running as a Kaapana extension, the new project namespace must be added manually to the Traefik `--providers.kubernetesingress.namespaces` list — see the [Deploying Projects](#deploying-projects-argocd-and-re-sync) section.

### 7. End user logs in

The user opens the login URL from the approval email, authenticates with their temp password, is forced to set a new password, and is redirected to the dashboard. They now see the project's JupyterHub, MinIO, MLflow, etc. on the project page.

### 8. Project deletion (only partially automated)

Clicking **Delete** on a project removes the Keycloak group via `delete_group_in_keycloak()`. The following are **not** cleaned up automatically — admins must do them by hand:

- ArgoCD application(s) for the project (delete from the ArgoCD UI).
- The Kubernetes namespace and any PVCs (delete after the ArgoCD apps are gone).
- MinIO bucket and any data it holds.
- The row in `maia_project_model` (no cascading delete).
- Any active GPU bookings tied to the project.
- Removal from the Traefik namespace list, if applicable.

A future enhancement would be a single "tear down project" action that fans these out; until then, follow this checklist in order.

### Common failure modes

| Symptom | Likely cause |
|---|---|
| User approval succeeds but no email arrives | SMTP env vars not set on the dashboard pod. Approval is silent. |
| Linking a user to a project succeeds but they cannot log in to MinIO/JupyterHub | `MAIA:users` group missing in Keycloak — the silent `try/except` masks the error. |
| Project namespace differs from what was requested | `_` is replaced with `-` and the name is lowercased. Plan project IDs accordingly. |
| Deploy fails with "no such storage class" | `shared_storage_class` in the dashboard ConfigMap doesn't exist on the target cluster. |
| Project ingress returns 404 under Kaapana | Traefik namespace list not updated to include the new project namespace. |


## User Management

### Registering a New User

To register a new user, the user must fill out the registration form with their username and email address. The request is then sent to the administrators for approval.
MAIA administrators can approve the user registration request by clicking on the "ID" icon, the top one next to the user entry. By clicking on the "ID" icon, the corresponding Keycloak user will be created and the user will be able to log in to the MAIA Dashboard. Once the User is correctly registered to Keycloak, the same icon will be replaced by a green check mark.
<p align="center">
    <img src="https://raw.githubusercontent.com/minnelab/maia/master/dashboard/docs/images/User_Registration.png" alt="MAIA Apps" width="40%">
</p>

### Linking a User to an Existing Project

The user can link their account in the registration form, where they can select the project they want to be linked to. 
In the Users page, MAIA administrators can approve the user liking request to a project by clicking on the "group" icon, the middle one next to the user entry. By clicking on the "group" icon. By clicking on the "group" icon, the corresponding Keycloak user will be assigned to the Keycloak group corresponding to the project. Once the User is correctly linked to the project, the same icon will be replaced by a green check mark.
A list of all the users part of the project is available in the same page
<p align="center">
    <img src="https://raw.githubusercontent.com/minnelab/maia/master/dashboard/docs/images/Admin_User_Registration.png" alt="MAIA Apps" width="40%">
</p>
If a user wishes to be removed from a project, administrators can unlink the user by updating the project list in the user's entry and clicking the unlink icon. Once unlinked, the user will lose access to the project's resources and tools.



## Project Management

### Approving Project Requests

Users can request a new project by filling out the project request form. The request is then sent to the administrators for approval.
The requested project will appear in the Projects and Users pages, where MAIA administrators can approve it by registering the corresponding Keycloak group and deploying the MAIA Namespace in the cluster. The Keycloak group will be created by clicking on the "group" icon, the top one on the first column next to the project entry. 
<p align="center">
    <img src="https://raw.githubusercontent.com/minnelab/maia/master/dashboard/docs/images/Project_Registration_user.png" alt="MAIA Apps" width="40%">
</p>

### Deploying Projects [ArgoCD and Re-Sync]
The MAIA Namespace can be deployed by clicking on the "deploy" icon, on the second column next to the project entry. By clicking on the "deploy" icon, the corresponding ArgoCD application will be created and the project will be deployed in the cluster. Once the Project is correctly registered to Keycloak and deployed in the cluster, the same icons will be replaced by the "update" button.

<p align="center">
    <img src="https://raw.githubusercontent.com/minnelab/maia/master/dashboard/docs/images/Project_Registration.png" alt="MAIA Apps" width="40%">
</p>

IMPORTANT!

If MAIA is deployed as an extension in Kaapana, you will need to enable the corresponding project namespace in the Traefik deployment(in the `admin` namespace):
```bash
--providers.kubernetesingress.namespaces=admin,jobs,services,extensions,<project_1>,<project_2>,...
```

### Deleting Projects

Upon completion of a project, the MAIA administrators can delete the project. This is done in two steps:
1. Deleting the Keycloak group: This is done by clicking on the "Delete" button. By clicking on the "Delete" button, the corresponding Keycloak group will be deleted and the users will no longer be associated with the group.
2. Manually deleting the ArgoCD applications: this must be done manually by the MAIA administrators, by going to the ArgoCD dashboard and deleting the corresponding applications. Once the applications and the ArgoCD project are deleted, the administrators can delete the namespace in the cluster.


## Resource Management

### Monitoring Cluster Status
The MAIA Dashboard Home page provides an overview of the MAIA cluster status, with one table for each cluster. The tables display the number of nodes per cluster and their current status (e.g., Ready, NotReady, UnderMaintenance). In addition, for each cluster, it is possible to navigate to the cluster's available monitoring services, such as Grafana and Kubernetes Dashboard, and other relevant applications, such as the Traefik dashboard, Rancher, ArgoCD, Keycloak and the Harbor registry.

<p align="center">
    <img src="https://raw.githubusercontent.com/minnelab/maia/master/dashboard/docs/images/Clusters.png" alt="MAIA Clusters" width="80%">
</p>

### Monitoring GPU Allocations

The MAIA Dashboard features a *Resources* page dedicated to tracking GPU usage across all projects. This page displays a table listing each allocated GPU, the associated project, and the requesting user, enabling administrators to monitor GPU utilization and optimize resource allocation.

Additionally, a filter below the GPU allocation table allows administrators to sort nodes by requested resources, including CPU, Memory, and GPU. This makes it easy to identify nodes that match specific requirements and locate available computing resources within the clusters.


### GPU Booking System

This system is implemented only for a subset of GPUs. The way it works is that users need to book a GPU in order to be able to use it. TThe booking is done through the *Book a GPU* page, where the user inserts the required information, such as the project, the GPU type, and the booking duration. Once the booking is confirmed, the user will receive an email notification with the booking details.
The booked GPU will be displayed in the *My GPU Booking* page, where the user can see the status of their bookings and any relevant information.
It is also possible to cancel a booking, which will free up the GPU for other users. The cancellation can be done by clicking on the "Delete" button next to the booking entry in the *My GPU Booking* page.

<p align="center">
    <img src="https://raw.githubusercontent.com/minnelab/maia/master/dashboard/docs/images/GPU_booking.png" alt="MAIA Clusters" width="40%">
</p>

<p align="center">
    <img src="https://raw.githubusercontent.com/minnelab/maia/master/dashboard/docs/images/gpu_booking.png" alt="MAIA Clusters" width="90%">
</p>

## Automatic Email Notifications

Automatic email notifications are used to welcome new users, notify them of project approvals, and inform them about resource allocations (including the GPU Booking system). The email notifications are sent to the user's registered email address and contain important information about their account and project status.

To enable email notifications, the MAIA administrators must configure the email settings in the MAIA Dashboard. This includes setting up the SMTP server, sender email address, and other relevant parameters:
```yaml
email_account:  <SMTP email address>
email_smtp_server: <SMTP server address>
email_password: <SMTP server password>
```