<template>
  <div class="app-root">
    <header class="topnav">
      <div class="shell topnav-inner">
        <RouterLink class="brand" to="/">
          <span class="brand-mark">RD-Agent Academy</span>
          <span class="brand-sub">Learn Lab</span>
        </RouterLink>
        <nav class="nav-links">
          <RouterLink to="/learn">课程</RouterLink>
          <RouterLink to="/map">流程地图</RouterLink>
          <RouterLink to="/lab">实验室</RouterLink>
        </nav>
      </div>
    </header>
    <RouterView />
  </div>
</template>

<script setup>
</script>