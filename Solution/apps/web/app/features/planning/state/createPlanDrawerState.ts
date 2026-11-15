import { ref, watch, type Ref } from 'vue'

/** Keep an empty draft compact; reveal its first stop and retain manual choices while populated. */
export function createPlanDrawerState(stopCount: Readonly<Ref<number>>) {
  const collapsed = ref(stopCount.value === 0)
  watch(stopCount, (count, previous) => {
    if (count === 0) collapsed.value = true
    else if (previous === 0) collapsed.value = false
  }, { flush: 'sync' })
  function toggle() { collapsed.value = !collapsed.value }
  return { collapsed, toggle }
}
