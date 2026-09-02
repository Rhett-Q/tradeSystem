import { createRouter, createWebHistory } from 'vue-router'
import HomeView from './views/HomeView.vue'
import LearnView from './views/LearnView.vue'
import LessonView from './views/LessonView.vue'
import LabView from './views/LabView.vue'
import MapView from './views/MapView.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/learn', name: 'learn', component: LearnView },
    { path: '/learn/:id', name: 'lesson', component: LessonView, props: true },
    { path: '/lab', name: 'lab', component: LabView },
    { path: '/lab/:panel', name: 'lab-panel', component: LabView, props: true },
    { path: '/map', name: 'map', component: MapView },
  ],
  scrollBehavior() {
    return { top: 0 }
  },
})