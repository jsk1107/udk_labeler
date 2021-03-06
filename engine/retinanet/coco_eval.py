# Original author: Yann Henon
# Adapted from https://github.com/yhenon/pytorch-retinanet/blob/master/retinanet/coco_eval.py
# Modified by jsk1107

from pycocotools.cocoeval import COCOeval
import json
import torch
from engine.retinanet.post_process import post_process
from engine.retinanet.utils import BBoxTransform, ClipBoxes

regress_boxes = BBoxTransform()
clip_boxes = ClipBoxes()


def evaluate_coco(dataset, model, json_path, threshold=0.05):
    
    model.eval()
    with torch.no_grad():

        # start collecting results
        results = []
        image_ids = []

        for index in range(len(dataset)):
            data = dataset[index]
            scale = data['scale']

            # run network
            img = data['img'].permute(2, 0, 1).cuda().float().unsqueeze(dim=0)
            classification, regression, anchors = model(img)
            scores, labels, boxes = post_process(img, classification, regression, anchors, regress_boxes, clip_boxes)

            # correct boxes for image scale
            boxes /= scale

            if boxes.shape[0] > 0:

                scores = scores.cpu()
                labels = labels.cpu()
                boxes = boxes.cpu()

                # change to (x, y, w, h) (MS COCO standard)
                boxes[:, 2] -= boxes[:, 0]
                boxes[:, 3] -= boxes[:, 1]

                # compute predicted labels and scores
                for box_id in range(boxes.shape[0]):
                    score = float(scores[box_id])
                    label = int(labels[box_id])
                    box = boxes[box_id, :]

                    # scores are sorted, so we can break
                    if score < threshold:
                        break

                    # append detection for each positively labeled class
                    image_result = {
                        'image_id'    : dataset.image_ids[index],
                        'category_id' : dataset.label_to_coco_label(label),
                        'score'       : float(score),
                        'bbox'        : box.tolist(),
                    }

                    # append detection to results
                    results.append(image_result)
            # append image to list of processed images
            image_ids.append(dataset.image_ids[index])

            # print progress
            print('{}/{}'.format(index, len(dataset)), end='\r')

        if not len(results):
            return

        # write output
        print(f'json_path: {json_path}')
        json.dump(results, open(f'{json_path}/{dataset.set_name}_bbox_results.json', 'w'), indent=4)

        # load results in COCO evaluation tool
        coco_true = dataset.coco
        coco_pred = coco_true.loadRes(f'{json_path}/{dataset.set_name}_bbox_results.json')

        # run COCO evaluation
        coco_eval = COCOeval(coco_true, coco_pred, 'bbox')
        coco_eval.params.imgIds = image_ids
        coco_eval.evaluate()
        coco_eval.accumulate()
        coco_eval.summarize()
        stats = coco_eval.stats
        return stats
