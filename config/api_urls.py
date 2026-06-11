"""Aggregated `/api/v1/` surface (architecture §7).

Public read + form-write + auth + admin (RBAC) + SEO meta. Sitemap/robots are
mounted at the site root in `config/urls.py`, not here.
"""
from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.audit.admin_api import AuditLogViewSet
from apps.blog.admin_api import AdminBlogPostViewSet
from apps.blog.views import BlogCategoryViewSet, BlogPostViewSet, TagViewSet
from apps.careers.admin_api import AdminApplicationViewSet
from apps.careers.views import JobApplicationCreateView, JobOpeningViewSet
from apps.core import api as core_api
from apps.core.admin_api import dashboard_stats
from apps.core.api import OfficeViewSet
from apps.leads.admin_api import AdminLeadViewSet
from apps.leads.views import LeadCreateView
from apps.newsletter import views as newsletter_views
from apps.projects.admin_api import AdminProjectViewSet
from apps.projects.views import ProjectCategoryViewSet, ProjectViewSet
from apps.seo.views import seo_meta
from apps.team.admin_api import AdminTeamMemberViewSet
from apps.team.views import TeamMemberViewSet
from apps.testimonials.admin_api import AdminTestimonialViewSet
from apps.testimonials.views import TestimonialViewSet
from apps.users import api as auth_api

# --- Public read ---
# NB: register sub-resources (categories/tags) BEFORE their parent detail
# viewset, else the parent's `/<slug>` route would swallow `/categories`.
public = DefaultRouter(trailing_slash=False)
public.register("projects/categories", ProjectCategoryViewSet, basename="project-categories")
public.register("projects", ProjectViewSet, basename="projects")
public.register("blog/categories", BlogCategoryViewSet, basename="blog-categories")
public.register("blog/tags", TagViewSet, basename="blog-tags")
public.register("blog", BlogPostViewSet, basename="blog")
public.register("team", TeamMemberViewSet, basename="team")
public.register("testimonials", TestimonialViewSet, basename="testimonials")
public.register("careers/openings", JobOpeningViewSet, basename="openings")
public.register("offices", OfficeViewSet, basename="offices")

# --- Public write (forms) ---
forms = DefaultRouter(trailing_slash=False)
forms.register("leads", LeadCreateView, basename="leads")
forms.register("careers/applications", JobApplicationCreateView, basename="applications")

# --- Admin (RBAC) ---
admin_router = DefaultRouter(trailing_slash=False)
admin_router.register("leads", AdminLeadViewSet, basename="admin-leads")
admin_router.register("applications", AdminApplicationViewSet, basename="admin-applications")
admin_router.register("audit-logs", AuditLogViewSet, basename="admin-audit")
admin_router.register("projects", AdminProjectViewSet, basename="admin-projects")
admin_router.register("blog", AdminBlogPostViewSet, basename="admin-blog")
admin_router.register("team", AdminTeamMemberViewSet, basename="admin-team")
admin_router.register("testimonials", AdminTestimonialViewSet, basename="admin-testimonials")

auth_patterns = [
    path("login", auth_api.login, name="login"),
    path("refresh", auth_api.refresh, name="refresh"),
    path("logout", auth_api.logout, name="logout"),
    path("me", auth_api.me, name="me"),
    path("password/change", auth_api.change_password, name="password-change"),
    path("password/reset/request", auth_api.password_reset_request, name="password-reset-request"),
    path("password/reset/confirm", auth_api.password_reset_confirm, name="password-reset-confirm"),
]

newsletter_patterns = [
    path("subscribe", newsletter_views.subscribe, name="subscribe"),
    path("confirm", newsletter_views.confirm, name="confirm"),
    path("unsubscribe", newsletter_views.unsubscribe, name="unsubscribe"),
]

urlpatterns = [
    path("", include(public.urls)),
    path("", include(forms.urls)),
    path("settings", core_api.settings_view, name="settings"),
    path("pages/<slug:key>", core_api.page_detail, name="page-detail"),
    path("seo/meta", seo_meta, name="seo-meta"),
    path("newsletter/", include(newsletter_patterns)),
    path("auth/", include(auth_patterns)),
    path("admin/", include(admin_router.urls)),
    path("admin/dashboard/stats", dashboard_stats, name="admin-dashboard-stats"),
]
