export FREESURFER_HOME=/usr/local/freesurfer/8.2.0
source $FREESURFER_HOME/SetUpFreeSurfer.sh

mri_synthstrip -i IXI169-Guys-0842-T1.nii -o IXI169_brain.nii.gz
