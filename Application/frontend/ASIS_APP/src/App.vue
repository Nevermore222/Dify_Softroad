<template>
  <div id="app">
    <router-view/>
    <TableManagement />
  </div>
</template>

<script setup>
import TableManagement from './components/TableManagement.vue'
</script>