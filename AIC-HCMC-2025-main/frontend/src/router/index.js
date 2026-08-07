import { createRouter, createWebHistory } from 'vue-router'


const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/' ,
      name: 'myhome',
      component: () => import('../views/KPTView.vue'),
    },
    {
      path: '/kpt',
      name: 'kpt',
      component: () => import('../views/SetIP.vue'),
    }
  ],
})

export default router
