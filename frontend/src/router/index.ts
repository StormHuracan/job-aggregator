import { createRouter, createWebHistory } from "vue-router";

import { ApiError } from "../api/client";
import { getCurrentUser, type CurrentUser } from "../api/user";
import AccountView from "../views/AccountView.vue";
import LoginView from "../views/LoginView.vue";
import NotFoundView from "../views/NotFoundView.vue";
import SavedSearchesView from "../views/SavedSearchesView.vue";
import VacanciesView from "../views/VacanciesView.vue";

type CurrentUserLoader = () => Promise<CurrentUser>;

export function createAppRouter(
  loadCurrentUser: CurrentUserLoader = getCurrentUser,
) {
  const router = createRouter({
    history: createWebHistory(),
    routes: [
      { path: "/", redirect: "/vacancies" },
      { path: "/login", component: LoginView },
      {
        path: "/account",
        component: AccountView,
        meta: { requiresAuth: true },
      },
      {
        path: "/vacancies",
        component: VacanciesView,
        meta: { requiresAuth: true },
      },
      {
        path: "/saved-searches",
        component: SavedSearchesView,
        meta: { requiresAuth: true },
      },
      { path: "/:pathMatch(.*)*", name: "not-found", component: NotFoundView },
    ],
  });

  router.beforeEach(async (to) => {
    if (!to.meta.requiresAuth) return true;
    try {
      const user = await loadCurrentUser();
      if (!user || !Number.isSafeInteger(user.id) || user.id <= 0) {
        throw new Error("Invalid session response");
      }
      return true;
    } catch (error) {
      return {
        path: "/login",
        query: {
          redirect: to.fullPath,
          reason:
            error instanceof ApiError && error.status === 401
              ? "auth-required"
              : "session-check-failed",
        },
      };
    }
  });

  return router;
}

export default createAppRouter();
