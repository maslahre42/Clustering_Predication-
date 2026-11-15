import test from 'node:test'
import assert from 'node:assert/strict'
import { component, mount, h, ref, nextTick } from './helpers/vue.mjs'
const Button={props:['label','loading','disabled'],emits:['click'],render(){return h('button',{disabled:this.loading||this.disabled,onClick:()=>this.$emit('click')},this.label)}}
const Card={render(){return h('section',{},this.$slots.default?.())}}
const Icon={render(){return h('span')}}
function setup(t){
 const source=ref(null),metadata=ref(null),view=ref('status')
 globalThis.useState=(key)=>key==='proposal-dataset'?source:metadata
 globalThis.useWorkspaceNavigation=()=>({view})
 globalThis.useWorkspaceData=()=>({asOf:ref('2026-09-30'),ready:ref(true),loading:ref(false),retry(){},bins:ref([{},{}]),clusters:ref([{}]),snapshotRequest:{data:ref({observationCount:20,firstDate:'2026-01-01',lastDate:'2026-09-30'})},healthRequest:{data:ref({status:'healthy'}),error:ref(null),status:ref('success')}})
 t.after(()=>{for(const key of ['useState','useWorkspaceNavigation','useWorkspaceData','$fetch'])delete globalThis[key]})
 return{source,metadata,view}
}
const summary={rows:3,locations:1,bins:1,firstDate:'2026-01-01',lastDate:'2026-09-01',materials:{brown:0,green:0,white:3},warnings:[],fingerprint:'abc',source:'uploaded-csv'}
const controls={UiCard:Card,UiButton:Button,UiIcon:Icon,UiTag:Icon}
test('actual drop zone validates the file before showing its active summary and forecasting link',async t=>{
 const f=setup(t);let sent;globalThis.$fetch=async(url,options)=>{sent={url,...options};return summary}
 const m=mount(t,await component('SystemStatus'),{},undefined,controls)
 const zone=m.all().find(n=>n.props['aria-label']==='CSV upload drop zone')
 zone.props.onDragenter({preventDefault(){},dataTransfer:{types:['Files']}});await nextTick();assert.ok(zone.props.class.includes('is-dragging'))
 await zone.props.onDrop({preventDefault(){},stopPropagation(){},dataTransfer:{files:[{name:'dropped.csv',size:10,text:async()=>'CSV ROWS'}]}});await nextTick();await nextTick()
 assert.equal(sent.url,'/api/dataset-validation');assert.equal(sent.body.csv,'CSV ROWS');assert.equal(sent.query.asOf,'2026-09-30')
 assert.equal(f.source.value.name,'dropped.csv');assert.match(m.text(),/dropped.csv is ready/);assert.match(m.text(),/CSV checked and ready/)
 m.all().find(n=>n.tag==='button'&&n.text==='Open forecasts & optimization').props.onClick();assert.equal(f.view.value,'forecasts')
 m.all().find(n=>n.tag==='button'&&n.text==='Use collection database').props.onClick();await nextTick();assert.equal(f.source.value,null);assert.equal(f.metadata.value,null)
})
test('actual file picker and rejected-row message preserve the active source',async t=>{
 const f=setup(t);f.source.value={name:'active.csv',csv:'keep'};f.metadata.value=summary
 globalThis.$fetch=async()=>{throw{data:{validation:{errors:[{row_number:2,message:'Fill must be 0–100'}]}}}}
 const m=mount(t,await component('SystemStatus'),{},undefined,controls)
 const picker=m.all().find(n=>n.tag==='input'&&n.props.type==='file');picker.files=[{name:'invalid.csv',size:10,text:async()=>'invalid'}]
 await picker.props.onChange({target:picker});await nextTick()
 assert.equal(f.source.value.name,'active.csv');assert.match(m.text(),/Row 3: Fill must be 0–100/);assert.match(m.text(),/active dataset is unchanged/)
})
