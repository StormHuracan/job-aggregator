import { createRouter, createWebHistory } from "vue-router";

import { ApiError } from "../api/client";
import type { CurrentUser } from "../api/user";
import { accountFixture } from "../mocks/user";
import AccountView from "../views/AccountView.vue";
import LoginView from "../views/LoginView.vue";
import NotFoundView from "../views/NotFoundView.vue";
import SavedSearchesView from "../views/SavedSearchesView.vue";
import VacanciesView from "../views/VacanciesView.vue";

type CurrentUserLoader = () => Promise<CurrentUser>;

export function createAppRouter(loadCurrentUser: CurrentUserLoader = accountFixture.getCurrentUser) {
  const router = createRouter({
    history: createWebHistory(),
    routes: [
      { path: "/", redirect: "/vacancies" },
      { path: "/login", component: LoginView },
      { path: "/account", component: AccountView, meta: { requiresAuth: true } },
      { path: "/vacancies", component: VacanciesView, meta: { requiresAuth: true } },
      { path: "/saved-searches", component: SavedSearchesView, meta: { requiresAuth: true } },
      { path: "/:pathMatch(.*)*", name: "not-found", component: NotFoundView },
    ],
  });

  router.beforeEach(async (to) => {
    if (!to.meta.requiresAuth) return true;
    try {
      await loadCurrentUser();
      return true;
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        return { path: "/login", query: { redirect: to.fullPath } };
      }
      return true;
    }
  });

  return router;
}

export default createAppRouter();
