window.config = {
  routerBasename: 'INGRESS_PATH/ohif/',
  showStudyList: true,
  extensions: [],
  modes: [],
  // below flag is for performance reasons, but it might not work for all servers

  showWarningMessageForCrossOrigin: true,
  showCPUFallbackMessage: true,
  showLoadingIndicator: true,
  strictZSpacingForVolumeViewport: true,
  defaultDataSourceName: 'dicomweb',
  useSharedArrayBuffer: 'FALSE',
  dataSources: [
    {
      namespace: '@ohif/extension-default.dataSourcesModule.dicomweb',
      sourceName: 'dicomweb',
      configuration: {
        friendlyName: 'Orthanc Server',
        name: 'Orthanc',
        wadoUriRoot: 'INGRESS_PATH/proxy/dicom/wado',
        qidoRoot: 'INGRESS_PATH/proxy/dicom/qido',
        wadoRoot: 'INGRESS_PATH/proxy/dicom/wado',
        qidoSupportsIncludeField: true,
        supportsReject: true,
        imageRendering: 'wadors',
        thumbnailRendering: 'wadors',
        enableStudyLazyLoad: false,
        supportsFuzzyMatching: true,
        supportsWildcard: true,
        dicomUploadEnabled: true,
        bulkDataURI: {
          enabled: true,
        },
      },
    },
  ],
};