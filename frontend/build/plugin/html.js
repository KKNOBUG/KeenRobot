import { createHtmlPlugin } from 'vite-plugin-html'

export function configHtmlPlugin(viteEnv, isBuild) {
  const { VITE_TITLE } = viteEnv

  return createHtmlPlugin({
    minify: isBuild,
    inject: {
      data: {
        title: VITE_TITLE,
      },
    },
  })
}
