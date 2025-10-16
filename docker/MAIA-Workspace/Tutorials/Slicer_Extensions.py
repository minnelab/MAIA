import slicer



def load_extensions(extensions):
    manager = slicer.app.extensionsManagerModel()
    for extension in extensions:
        manager.downloadAndInstallExtensionByName(extension)


if __name__ == "__main__":
    extensions = [
        "DICOMwebBrowser",
        "MONAILabel",
        "DCMQI",
        "PETDICOMExtension",
        "SegmentEditorExtraEffects",
        "SlicerConda",
        #"SlicerDevelopmentToolbox",
        #"DatabaseInteractor",
        #"DebuggingTools",
        #"MarkupsToModel",
        #"Chest_Imaging_Platform",
        #"MONAIViz",
        #"MatlabBridge",
        #"NvidiaAIAssistedAnnotation",
        "PETTumorSegmentation",
        #"PyTorch",
        "QuantitativeReporting",
        #"SkullStripper",
        #"SlicerBatchAnonymize",
        #"SlicerRT",
        #"SlicerRadiomics",
        #"SegmentationVerification",
        #"TorchIO",
        #"LungCTAnalyzer",
        "TotalSegmentator",
        "MONAIAuto3DSeg",
        "SegmentWithSAM",
        "SlicerDcm2nii",
        "TCIABrowser",
        "nnUNet",
        "NNInteractive",
        "ImageAugmenter",
        "XNATSlicer",
        "SlicerFreeSurfer",
    ]

    load_extensions(extensions)