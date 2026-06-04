import vue from '@vitejs/plugin-vue'
import Unocss from 'unocss/vite'
import { configHtmlPlugin } from './html.js'
import unplugin from './unplugin.js'

export function createVitePlugins(viteEnv, isBuild) {
  return [vue(), ...unplugin, configHtmlPlugin(viteEnv, isBuild), Unocss()]
}
